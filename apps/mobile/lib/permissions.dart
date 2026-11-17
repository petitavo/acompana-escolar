import 'dart:async';
import 'package:flutter/material.dart';

/// Pasos de la guía "Prepara tu teléfono". Cada permiso explica para qué sirve,
/// qué NO se recoge y cómo activarlo según la marca del teléfono.
class SetupStep {
  const SetupStep({
    required this.kind,
    required this.title,
    required this.icon,
    required this.why,
    required this.notSeen,
    required this.how,
    this.preference,
  });
  final String kind;
  final String title;
  final IconData icon;
  final List<String> why;
  final List<String> notSeen;
  final String how;

  /// Preferencia de participación que respalda este permiso (null = ajuste del teléfono).
  final String? preference;
}

String brandOf(Map device) {
  final b = '${device['manufacturer'] ?? ''} ${device['brand'] ?? ''}'
      .toLowerCase();
  for (final name in [
    'xiaomi',
    'redmi',
    'poco',
    'samsung',
    'huawei',
    'honor',
    'oppo',
    'realme',
    'oneplus',
    'vivo',
    'motorola',
  ]) {
    if (b.contains(name)) {
      return {'redmi': 'xiaomi', 'poco': 'xiaomi'}[name] ?? name;
    }
  }
  return 'android';
}

const brandNames = {
  'xiaomi': 'Xiaomi / Redmi / POCO',
  'samsung': 'Samsung',
  'huawei': 'Huawei',
  'honor': 'Honor',
  'oppo': 'OPPO',
  'realme': 'realme',
  'oneplus': 'OnePlus',
  'vivo': 'vivo',
  'motorola': 'Motorola',
  'android': 'Android',
};

/// Marcas que cierran apps en segundo plano y tienen un ajuste de "inicio automático".
const autostartBrands = {
  'xiaomi',
  'huawei',
  'honor',
  'oppo',
  'realme',
  'oneplus',
  'vivo',
};

List<SetupStep> setupSteps(Map status, Map device) {
  final brand = brandOf(device);
  final steps = <SetupStep>[
    const SetupStep(
      kind: 'notifications',
      preference: 'reminders',
      title: 'Avisos',
      icon: Icons.notifications_active_outlined,
      why: [
        'Recordarte cuando tengas un cuestionario pendiente.',
        'Avisarte si el equipo de psicología te propone una cita.',
      ],
      notSeen: [
        'No enviamos publicidad.',
        'Los avisos no muestran tus respuestas.',
      ],
      how: 'Toca "Permitir" y luego "Permitir" en la ventana de Android.',
    ),
    SetupStep(
      kind: 'usage',
      preference: 'usage',
      title: 'Uso de pantalla',
      icon: Icons.phone_android,
      why: const [
        'Contar cuántas veces y cuánto tiempo se enciende la pantalla.',
        'Estimar a qué hora dejas el celular por la noche y cuándo lo vuelves a usar (tu descanso).',
      ],
      notSeen: const [
        'No vemos qué apps usas.',
        'No vemos mensajes, fotos, llamadas ni lo que escribes.',
      ],
      how:
          'Se abrirá una lista de Ajustes. Busca "Acompaña Escolar", tócala y activa el interruptor. Luego vuelve con la flecha de atrás. Android muestra un aviso general que dice que la app podría ver qué apps usas: es el texto estándar de este permiso. Acompaña Escolar solo cuenta cuándo se enciende y se apaga la pantalla y no guarda nombres de apps. Si aparece "Configuración restringida" o "Se le negó el acceso": cierra ese aviso, ve a Ajustes → Aplicaciones → Acompaña Escolar, toca ⋮ (arriba a la derecha) → "Permitir configuración restringida" y vuelve a intentar. Pasa solo cuando la app se instaló fuera de Play Store.${{'xiaomi': ' En Xiaomi la lista se llama "Acceso a datos de uso".', 'samsung': ' En Samsung la lista se llama "Acceso a datos de uso".', 'huawei': ' En Huawei la lista se llama "Acceso al uso de apps".', 'honor': ' En Honor la lista se llama "Acceso al uso de apps".'}[brand] ?? ''}',
    ),
    const SetupStep(
      kind: 'location',
      preference: 'location',
      title: 'Ubicación',
      icon: Icons.location_on_outlined,
      why: [
        'Calcular cuánto te mueves durante el día y el tiempo que pasas en casa.',
        'Saber si estuviste en el colegio en horario de clases (asistencia).',
      ],
      notSeen: [
        'Nadie ve un mapa de dónde estás.',
        'Tus coordenadas se quedan en tu teléfono; solo se envían resúmenes, por ejemplo "3 km recorridos".',
      ],
      how:
          'Toca "Permitir". En la ventana de Android elige "Mientras la app está en uso" y deja activada "Ubicación precisa".',
    ),
  ];
  if (['precise', 'approximate'].contains(status['location_permission'])) {
    steps.add(
      SetupStep(
        kind: 'background',
        preference: 'location',
        title: 'Ubicación con la app cerrada',
        icon: Icons.my_location,
        why: const [
          'Que los resúmenes de movimiento sigan funcionando aunque no abras la app.',
        ],
        notSeen: const [
          'Lo mismo que antes: solo resúmenes. Verás una notificación fija mientras esté activo y puedes pausarlo cuando quieras.',
        ],
        how:
            'Al tocar "Abrir ajustes" se abrirá la pantalla de ubicación de la app (Android ya no permite pedirlo con una ventana). Elige ${brand == 'xiaomi' ? '"Permitir siempre"' : '"Permitir todo el tiempo"'}. Luego vuelve con la flecha de atrás.',
      ),
    );
  }
  if (status['steps_supported'] != false) {
    steps.add(
      const SetupStep(
        kind: 'steps',
        preference: 'steps',
        title: 'Pasos',
        icon: Icons.directions_walk,
        why: ['Contar tus pasos con el sensor del teléfono.'],
        notSeen: [
          'No mide toda tu actividad física, solo cuando llevas el teléfono.',
        ],
        how:
            'Toca "Permitir" y en la ventana de Android elige "Permitir" (actividad física).',
      ),
    );
  }
  steps.add(
    SetupStep(
      kind: 'battery',
      title: 'Batería sin restricciones',
      icon: Icons.battery_charging_full,
      why: const [
        'Android "duerme" las apps que no abres seguido. Si pasa, los datos dejan de enviarse.',
      ],
      notSeen: const [
        'Este ajuste no da acceso a nada nuevo: no vemos tu batería, tus apps ni tus datos.',
        'Solo evita que Android cierre la app. Usa poca batería: revisa la ubicación cada 15 minutos y envía datos en grupo.',
      ],
      how:
          'Toca "Quitar restricción" y elige "Permitir".${{'samsung': ' Si no aparece la ventana: Ajustes → Aplicaciones → Acompaña Escolar → Batería → "Sin restricciones".', 'xiaomi': ' Si no aparece: Ajustes → Aplicaciones → Acompaña Escolar → Ahorro de batería → "Sin restricciones".', 'huawei': ' Si no aparece: Ajustes → Batería → Inicio de aplicaciones → Acompaña Escolar → "Administrar manualmente" y activa las tres opciones.', 'honor': ' Si no aparece: Ajustes → Batería → Inicio de aplicaciones → Acompaña Escolar → "Administrar manualmente".', 'oppo': ' Si no aparece: Ajustes → Batería → Acompaña Escolar → "Permitir actividad en segundo plano".', 'realme': ' Si no aparece: Ajustes → Batería → Acompaña Escolar → "Permitir actividad en segundo plano".'}[brand] ?? ''}',
    ),
  );
  if (autostartBrands.contains(brand) || device['autostart_screen'] == true) {
    steps.add(
      SetupStep(
        kind: 'autostart',
        title: 'Inicio automático',
        icon: Icons.restart_alt,
        why: [
          'En ${brandNames[brand] ?? 'tu teléfono'} hay un ajuste extra que cierra apps al reiniciar o limpiar la memoria.',
        ],
        notSeen: const [
          'Solo permite que la app vuelva a funcionar después de reiniciar el teléfono.',
        ],
        how:
            'Toca "Abrir ajuste", busca "Acompaña Escolar" y activa el interruptor de inicio automático. Vuelve y toca "Ya lo activé".${brand == 'xiaomi' ? ' Consejo: en la pantalla de apps recientes, mantén presionada Acompaña Escolar y toca el candado para que no se cierre.' : ''}',
      ),
    );
  }
  return steps;
}

/// Estado de un paso a partir del estado nativo y de la política guardada.
String stepState(SetupStep s, Map status, Map device, Map policy) {
  final granted = switch (s.kind) {
    'notifications' => status['notifications_permission'] == true,
    'usage' => status['usage_access'] == 'available',
    'location' => status['location_permission'] == 'precise',
    'background' => status['background_location'] == true,
    'steps' => status['steps_permission'] == true,
    'battery' =>
      status['battery_unrestricted'] == true ||
          device['battery_unrestricted'] == true,
    'autostart' => device['autostart_confirmed'] == true,
    _ => false,
  };
  if (s.kind == 'location' &&
      status['location_permission'] == 'approximate' &&
      policy['location'] == true) {
    return 'approximate';
  }
  if (s.preference != null && policy[s.preference] != true) {
    return 'off';
  }
  return granted ? 'ready' : 'pending';
}

const stateLabels = {
  'ready': 'Activo',
  'pending': 'Falta activar',
  'off': 'No compartido',
  'approximate': 'Solo aproximada',
};

Color stateColor(BuildContext context, String state) => switch (state) {
  'ready' => const Color(0xff0f766e),
  'approximate' => const Color(0xffb45309),
  'pending' => Theme.of(context).colorScheme.primary,
  _ => Colors.blueGrey,
};

/// Mensaje claro para cada resultado devuelto por Android.
String resultMessage(String? state, SetupStep step) => switch (state) {
  'granted' => '¡Listo! Este paso ya está activo.',
  'denied' =>
    'No se activó. No pasa nada: puedes intentarlo otra vez o seguir sin esto.',
  'blocked' =>
    step.kind == 'notifications'
        ? 'Android ya no muestra la ventana porque antes se rechazó. Toca "Abrir ajustes", entra a "Notificaciones" y activa "Permitir notificaciones".'
        : 'Android ya no muestra la ventana porque antes se rechazó. Toca "Abrir ajustes", entra a "Permisos" y activa ${step.title.toLowerCase()}.',
  'approximate' =>
    'Elegiste ubicación aproximada. Con ella no se pueden calcular recorridos. Toca "Usar ubicación precisa" y activa "Ubicación precisa".',
  'settings_opened' =>
    'Haz el cambio en Ajustes y vuelve con la flecha de atrás. Revisamos el resultado automáticamente.',
  'offline' =>
    'Tu elección se guardó, pero falta internet para confirmarla. Vuelve a tocar el botón cuando tengas conexión.',
  'unavailable' =>
    'Este teléfono no tiene ese ajuste. Puedes continuar con el siguiente paso.',
  _ => '',
};

class PermissionGuide extends StatefulWidget {
  const PermissionGuide({
    super.key,
    required this.loadStatus,
    required this.loadDevice,
    required this.policy,
    required this.request,
    required this.confirm,
    this.initialKind,
  });

  /// Devuelve el estado nativo actualizado (permisos concedidos).
  final Future<Map<String, dynamic>> Function() loadStatus;
  final Future<Map<String, dynamic>> Function() loadDevice;
  final Map Function() policy;

  /// Pide el permiso (guardando antes la preferencia si hace falta). Devuelve el resultado.
  final Future<String?> Function(String kind) request;

  /// Marca un ajuste que Android no permite comprobar (inicio automático).
  final Future<void> Function(String key) confirm;
  final String? initialKind;

  @override
  State<PermissionGuide> createState() => _PermissionGuideState();
}

class _PermissionGuideState extends State<PermissionGuide>
    with WidgetsBindingObserver {
  final pages = PageController();
  Map<String, dynamic> status = {}, device = {};
  int page = 0;
  bool busy = false, loaded = false;
  final results = <String, String>{};

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    reload().then((_) {
      final initial = widget.initialKind;
      if (initial != null && mounted) {
        final i = steps.indexWhere((s) => s.kind == initial);
        if (i >= 0) go(i + 1, animate: false);
      }
    });
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    pages.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState s) {
    // Al volver de Ajustes comprobamos de nuevo qué quedó activo.
    if (s == AppLifecycleState.resumed) reload();
  }

  List<SetupStep> get steps => setupSteps(status, device);

  Future<void> reload() async {
    try {
      final values = await Future.wait([
        widget.loadStatus(),
        widget.loadDevice(),
      ]);
      if (!mounted) return;
      setState(() {
        status = values[0];
        device = values[1];
        loaded = true;
        for (final s in steps) {
          if (stepState(s, status, device, widget.policy()) == 'ready') {
            results[s.kind] = 'granted';
          }
        }
      });
    } catch (_) {
      if (mounted) setState(() => loaded = true);
    }
  }

  void go(int i, {bool animate = true}) {
    final total = steps.length + 2;
    final target = i.clamp(0, total - 1);
    setState(() => page = target);
    if (!pages.hasClients) {
      // La primera vez el PageView aún no existe (se construye al terminar la
      // carga): saltar al paso pedido en el siguiente cuadro.
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && pages.hasClients) pages.jumpToPage(target);
      });
      return;
    }
    if (animate) {
      pages.animateToPage(
        target,
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeOut,
      );
    } else {
      pages.jumpToPage(target);
    }
  }

  Future<void> run(SetupStep step, {bool settings = false}) async {
    setState(() => busy = true);
    try {
      final result = await widget.request(settings ? 'settings' : step.kind);
      await reload();
      if (!mounted) return;
      final state = stepState(step, status, device, widget.policy());
      setState(() {
        results[step.kind] = state == 'ready'
            ? 'granted'
            : state == 'approximate'
            ? 'approximate'
            : (result ?? 'denied');
      });
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final list = steps;
    final total = list.length + 2;
    final policy = widget.policy();
    final readyCount = list
        .where((s) => stepState(s, status, device, policy) == 'ready')
        .length;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Prepara tu teléfono'),
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(4),
          child: LinearProgressIndicator(
            value: (page + 1) / total,
            minHeight: 4,
          ),
        ),
      ),
      body: !loaded
          ? const Center(child: CircularProgressIndicator())
          : PageView(
              controller: pages,
              physics: const NeverScrollableScrollPhysics(),
              onPageChanged: (i) => setState(() => page = i),
              children: [
                intro(list.length),
                for (var i = 0; i < list.length; i++)
                  stepPage(list[i], i, list.length, policy),
                summary(list, policy, readyCount),
              ],
            ),
    );
  }

  Widget frame(List<Widget> children, List<Widget> actions) => SafeArea(
    child: Column(
      children: [
        Expanded(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(22, 22, 22, 8),
            children: children,
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(22, 8, 22, 18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: actions,
          ),
        ),
      ],
    ),
  );

  Widget intro(int count) => frame(
    [
      const Icon(
        Icons.verified_user_outlined,
        size: 64,
        color: Color(0xff137c84),
      ),
      const SizedBox(height: 16),
      Text(
        'Vamos a preparar tu teléfono',
        style: Theme.of(context).textTheme.headlineSmall,
        textAlign: TextAlign.center,
      ),
      const SizedBox(height: 14),
      Text(
        'Son unos pocos pasos cortos (unos 3 minutos). En cada uno te explicamos para qué sirve y qué NO vemos.',
        textAlign: TextAlign.center,
      ),
      const SizedBox(height: 18),
      const _Bullet(
        icon: Icons.toggle_on_outlined,
        text: 'Todo es opcional. Puedes saltar cualquier paso con "Ahora no".',
      ),
      const _Bullet(
        icon: Icons.lock_outline,
        text:
            'Nunca leemos mensajes, fotos, llamadas ni lo que escribes. No vemos qué apps usas.',
      ),
      const _Bullet(
        icon: Icons.pause_circle_outline,
        text:
            'Puedes pausar o cambiar lo que compartes cuando quieras, en la pestaña Participación.',
      ),
    ],
    [FilledButton(onPressed: () => go(1), child: const Text('Empezar'))],
  );

  Widget stepPage(SetupStep s, int index, int count, Map policy) {
    final state = stepState(s, status, device, policy);
    final result = results[s.kind];
    final ready = state == 'ready';
    final blocked = result == 'blocked';
    final theme = Theme.of(context);
    String primaryLabel;
    VoidCallback? primary;
    if (ready) {
      primaryLabel = index == count - 1 ? 'Terminar' : 'Siguiente';
      primary = () => go(index + 2);
    } else if (blocked) {
      primaryLabel = 'Abrir ajustes';
      primary = () => run(s, settings: true);
    } else if (s.kind == 'autostart') {
      primaryLabel = 'Abrir ajuste';
      primary = () => run(s);
    } else if (s.kind == 'battery') {
      primaryLabel = 'Quitar restricción';
      primary = () => run(s);
    } else if (s.kind == 'background') {
      primaryLabel = 'Abrir ajustes';
      primary = () => run(s);
    } else if (state == 'approximate') {
      primaryLabel = 'Usar ubicación precisa';
      primary = () => run(s);
    } else {
      primaryLabel = 'Permitir';
      primary = () => run(s);
    }
    return frame(
      [
        Text(
          'Paso ${index + 1} de $count',
          style: theme.textTheme.labelLarge?.copyWith(
            color: theme.colorScheme.primary,
          ),
        ),
        const SizedBox(height: 10),
        Row(
          children: [
            CircleAvatar(
              radius: 26,
              backgroundColor: theme.colorScheme.primaryContainer,
              child: Icon(s.icon, color: theme.colorScheme.onPrimaryContainer),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Text(s.title, style: theme.textTheme.headlineSmall),
            ),
          ],
        ),
        const SizedBox(height: 10),
        Align(
          alignment: Alignment.centerLeft,
          child: Chip(
            label: Text(stateLabels[state] ?? state),
            labelStyle: TextStyle(color: stateColor(context, state)),
            side: BorderSide(color: stateColor(context, state)),
            avatar: Icon(
              ready ? Icons.check_circle : Icons.radio_button_unchecked,
              size: 18,
              color: stateColor(context, state),
            ),
          ),
        ),
        const SizedBox(height: 10),
        _Section(title: 'Para qué sirve', items: s.why, icon: Icons.check),
        _Section(title: 'Lo que NO vemos', items: s.notSeen, icon: Icons.block),
        if (!ready)
          _Section(
            title: 'Cómo hacerlo',
            items: [s.how],
            icon: Icons.touch_app_outlined,
          ),
        if (result != null && result != 'granted' ||
            ready && result == 'granted')
          Semantics(
            liveRegion: true,
            child: Container(
              margin: const EdgeInsets.only(top: 12),
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: ready
                    ? const Color(0xffe6f4f1)
                    : const Color(0xfffff4e5),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(
                ready ? resultMessage('granted', s) : resultMessage(result, s),
              ),
            ),
          ),
      ],
      [
        FilledButton(
          key: ValueKey('guide-$primaryLabel'),
          onPressed: busy ? null : primary,
          child: Text(primaryLabel),
        ),
        if (s.kind == 'autostart' && !ready) ...[
          const SizedBox(height: 8),
          OutlinedButton(
            onPressed: busy
                ? null
                : () async {
                    await widget.confirm('autostart');
                    await reload();
                    if (mounted) go(index + 2);
                  },
            child: const Text('Ya lo activé'),
          ),
        ],
        if (s.kind == 'usage' && !ready && results.containsKey('usage')) ...[
          const SizedBox(height: 8),
          // Android 13+ bloquea este permiso en apps instaladas fuera de Play Store
          // hasta "Permitir configuración restringida" en la info de la app.
          OutlinedButton(
            onPressed: busy ? null : () => run(s, settings: true),
            child: const Text('¿Android lo bloqueó? Abrir info de la app'),
          ),
        ],
        if (!ready)
          TextButton(
            onPressed: busy ? null : () => go(index + 2),
            child: const Text('Ahora no'),
          ),
      ],
    );
  }

  Widget summary(List<SetupStep> list, Map policy, int ready) => frame(
    [
      Icon(
        ready == list.length
            ? Icons.celebration_outlined
            : Icons.fact_check_outlined,
        size: 60,
        color: const Color(0xff137c84),
      ),
      const SizedBox(height: 12),
      Text(
        ready == list.length ? '¡Tu teléfono está listo!' : 'Resumen',
        style: Theme.of(context).textTheme.headlineSmall,
        textAlign: TextAlign.center,
      ),
      const SizedBox(height: 8),
      Text(
        '$ready de ${list.length} pasos activos. Puedes volver a esta guía desde Inicio o Participación.',
        textAlign: TextAlign.center,
      ),
      const SizedBox(height: 12),
      for (var i = 0; i < list.length; i++)
        Builder(
          builder: (context) {
            final state = stepState(list[i], status, device, policy);
            return ListTile(
              contentPadding: EdgeInsets.zero,
              leading: Icon(list[i].icon, color: stateColor(context, state)),
              title: Text(list[i].title),
              subtitle: Text(stateLabels[state] ?? state),
              trailing: state == 'ready'
                  ? Icon(Icons.check_circle, color: stateColor(context, state))
                  : TextButton(
                      onPressed: () => go(i + 1),
                      child: const Text('Activar'),
                    ),
            );
          },
        ),
    ],
    [
      FilledButton(
        onPressed: () => Navigator.of(context).pop(),
        child: const Text('Volver al inicio'),
      ),
    ],
  );
}

class _Section extends StatelessWidget {
  const _Section({
    required this.title,
    required this.items,
    required this.icon,
  });
  final String title;
  final List<String> items;
  final IconData icon;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: 12),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 6),
        for (final item in items) _Bullet(icon: icon, text: item),
      ],
    ),
  );
}

class _Bullet extends StatelessWidget {
  const _Bullet({required this.icon, required this.text});
  final IconData icon;
  final String text;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 4),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 18, color: Theme.of(context).colorScheme.primary),
        const SizedBox(width: 10),
        Expanded(child: Text(text)),
      ],
    ),
  );
}
