targetScope = 'resourceGroup'

param location string = resourceGroup().location
param vmSize string = 'Standard_B2als_v2'
param adminPublicKey string
@allowed(['azureuser'])
param adminUsername string = 'azureuser'
@description('IP pública del equipo administrador, con /32. SSH nunca se abre a todo Internet.')
param sshSourceCidr string

var prefix = 'acompana-lab'
var tags = { project: 'acompana-escolar', environment: 'LAB', purpose: 'adult-phone-test' }

resource publicIp 'Microsoft.Network/publicIPAddresses@2024-05-01' = {
  name: '${prefix}-ip'
  location: location
  tags: tags
  sku: { name: 'Standard' }
  properties: {
    publicIPAllocationMethod: 'Static'
    dnsSettings: { domainNameLabel: '${prefix}-${uniqueString(resourceGroup().id)}' }
  }
}

resource nsg 'Microsoft.Network/networkSecurityGroups@2024-05-01' = {
  name: '${prefix}-nsg'
  location: location
  tags: tags
  properties: {
    securityRules: [
      {
        name: 'web-https-acme'
        properties: {
          priority: 100
          access: 'Allow'
          direction: 'Inbound'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRanges: ['80', '443']
          sourceAddressPrefix: 'Internet'
          destinationAddressPrefix: '*'
        }
      }
      {
        name: 'ssh-administrator'
        properties: {
          priority: 110
          access: 'Allow'
          direction: 'Inbound'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '22'
          sourceAddressPrefix: sshSourceCidr
          destinationAddressPrefix: '*'
        }
      }
    ]
  }
}

resource vnet 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: '${prefix}-vnet'
  location: location
  tags: tags
  properties: {
    addressSpace: { addressPrefixes: ['10.47.0.0/16'] }
    subnets: [{ name: 'app', properties: { addressPrefix: '10.47.0.0/24', networkSecurityGroup: { id: nsg.id } } }]
  }
}

resource nic 'Microsoft.Network/networkInterfaces@2024-05-01' = {
  name: '${prefix}-nic'
  location: location
  tags: tags
  properties: {
    ipConfigurations: [{
      name: 'main'
      properties: {
        privateIPAllocationMethod: 'Dynamic'
        subnet: { id: '${vnet.id}/subnets/app' }
        publicIPAddress: { id: publicIp.id }
      }
    }]
  }
}

resource vm 'Microsoft.Compute/virtualMachines@2024-07-01' = {
  name: prefix
  location: location
  tags: tags
  properties: {
    hardwareProfile: { vmSize: vmSize }
    osProfile: {
      computerName: prefix
      adminUsername: adminUsername
      customData: base64(loadTextContent('cloud-init.yaml'))
      linuxConfiguration: {
        disablePasswordAuthentication: true
        ssh: { publicKeys: [{ path: '/home/${adminUsername}/.ssh/authorized_keys', keyData: adminPublicKey }] }
        provisionVMAgent: true
      }
    }
    storageProfile: {
      imageReference: { publisher: 'Canonical', offer: 'ubuntu-24_04-lts', sku: 'server', version: 'latest' }
      osDisk: { createOption: 'FromImage', diskSizeGB: 32, managedDisk: { storageAccountType: 'StandardSSD_LRS' } }
    }
    securityProfile: {
      securityType: 'TrustedLaunch'
      uefiSettings: { secureBootEnabled: true, vTpmEnabled: true }
    }
    networkProfile: { networkInterfaces: [{ id: nic.id }] }
  }
}

output hostname string = publicIp.properties.dnsSettings.fqdn
output ip string = publicIp.properties.ipAddress
output vmName string = vm.name
output url string = 'https://${publicIp.properties.dnsSettings.fqdn}'
