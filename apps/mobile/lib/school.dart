import 'dart:convert';
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

class SchoolApp extends StatelessWidget {
  const SchoolApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Acompaña Escolar',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xff137c84)),
      scaffoldBackgroundColor: const Color(0xfff4f7fb),
      inputDecorationTheme: const InputDecorationTheme(
        border: OutlineInputBorder(),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(50)),
      ),
    ),
    home: const SchoolHome(),
  );
}

class SchoolHome extends StatefulWidget {
  const SchoolHome({super.key});
  @override
  State<SchoolHome> createState() => _SchoolHomeState();
}

class _SchoolHomeState extends State<SchoolHome> with WidgetsBindingObserver {
  static const bridge = MethodChannel('pe.upc.acompana/collector');
  Map<String, dynamic> status = {}, home = {}, requests = {}, answers = {};
  List<dynamic> deliveryLog = [], responseHistory = [];
  Map<String, dynamic>? form;
  final server = TextEditingController(
    text: const String.fromEnvironment('API_URL'),
  );
  final invitation = TextEditingController(), code = TextEditingController();
  final scroll = ScrollController();
  int tab = 0;
  int? functioning;
  bool busy = false,
      accepted = false,
      refreshing = false,
      preferencesDirty = false;
  String message = '';
  Timer? refreshTimer;
  bool startingSensors = false, formsLoaded = false, formsUnavailable = false;
  bool sensorPermissionsChanged = false;
  bool usage = false,
      location = false,
      steps = false,
      raw = false,
      research = false,
      reminders = true;
  TimeOfDay reminder = const TimeOfDay(hour: 17, minute: 0);
  Future<void> correctHistory(Map<String, dynamic> row) async {
    final definition = Map<String, dynamic>.from(row['definition']);
    final corrected = Map<String, dynamic>.from(row['answers']);
    int? impact = row['functioning'];
    final reason = TextEditingController();
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, update) => AlertDialog(
          title: const Text('Corregir mi respuesta'),
          content: SizedBox(
            width: 520,
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Text(
                    'Corrige el mismo período. Conservaremos la respuesta anterior y las revisiones del equipo.',
                  ),
                  for (final q in definition['questions']) ...[
                    Text(q['text']),
                    DropdownButtonFormField<int>(
                      initialValue: corrected[q['id']],
                      items: [
                        for (final o in definition['options'])
                          DropdownMenuItem(
                            value: o['value'] as int,
                            child: Text(o['label']),
                          ),
                      ],
                      onChanged: (v) => update(() => corrected[q['id']] = v),
                    ),
                  ],
                  Text(definition['functioning']['text']),
                  DropdownButtonFormField<int>(
                    initialValue: impact,
                    items: [
                      for (final o
                          in (definition['functioning']['options'] as List)
                              .asMap()
                              .entries)
                        DropdownMenuItem(value: o.key, child: Text(o.value)),
                    ],
                    onChanged: (v) => update(() => impact = v),
                  ),
                  TextField(
                    controller: reason,
                    maxLength: 500,
                    decoration: const InputDecoration(
                      labelText: 'Motivo de la corrección',
                    ),
                    onChanged: (_) => update(() {}),
                  ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('Cancelar'),
            ),
            FilledButton(
              onPressed:
                  reason.text.trim().length >= 3 &&
                      (!corrected.values.any((v) => (v as int) > 0) ||
                          impact != null)
                  ? () => Navigator.pop(dialogContext, {
                      'answers': corrected,
                      'functioning': impact,
                      'reason': reason.text.trim(),
                    })
                  : null,
              child: const Text('Enviar corrección'),
            ),
          ],
        ),
      ),
    );
    reason.dispose();
    if (result != null && mounted) {
      await action('schoolCorrection', {
        'id': row['id'],
        'body': jsonEncode(result),
      });
    }
  }

  Widget historyCard() => card('Mis respuestas recibidas', [
    const Text(
      'Las correcciones conservan versiones anteriores. Los envíos sin conexión se muestran en Pendientes, hasta recibir confirmación.',
    ),
    if (responseHistory.isEmpty)
      const Text('Todavía no hay respuestas recibidas en este historial.'),
    for (final raw in responseHistory)
      Builder(
        builder: (context) {
          final row = Map<String, dynamic>.from(raw);
          final def = row['definition'];
          return ExpansionTile(
            title: Text('${row['applied_at']} · Versión ${row['revision']}'),
            subtitle: Text(
              row['current'] == true
                  ? 'Vigente · recibida'
                  : 'Versión anterior · conservada',
            ),
            children: [
              for (final q in def['questions'])
                ListTile(
                  title: Text(q['text']),
                  subtitle: Text(
                    '${def['options'].firstWhere((o) => o['value'] == row['answers'][q['id']])['label']}',
                  ),
                ),
              if (row['can_correct'] == true)
                TextButton(
                  onPressed: busy ? null : () => correctHistory(row),
                  child: const Text('Corregir esta respuesta'),
                ),
            ],
          );
        },
      ),
  ]);

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    refresh();
    refreshTimer = Timer.periodic(const Duration(seconds: 45), (_) {
      if (!busy &&
          WidgetsBinding.instance.lifecycleState == AppLifecycleState.resumed) {
        refresh();
      }
    });
  }

  @override
  void dispose() {
    refreshTimer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    server.dispose();
    invitation.dispose();
    code.dispose();
    scroll.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState s) {
    if (s == AppLifecycleState.resumed) refresh();
  }

  Future<dynamic> call(String method, [Map<String, dynamic>? args]) async {
    final text = await bridge.invokeMethod<String>(method, args);
    return text == null ? null : jsonDecode(text);
  }

  void applyHome(Map<String, dynamic> value) {
    if (!value.containsKey('authorization')) return;
    setState(() {
      home = value;
      if (!preferencesDirty) {
        final p = value['policy'] ?? {};
        usage = p['usage'] == true;
        location = p['location'] == true;
        steps = p['steps'] == true;
        raw = p['raw_location_upload'] == true;
        research = p['research_access'] == true;
        reminders = p['reminders'] != false;
        final parts = (p['reminder_time'] ?? '17:00').toString().split(':');
        final hour = int.tryParse(parts.first) ?? 17;
        final minute = parts.length > 1 ? int.tryParse(parts[1]) ?? 0 : 0;
        reminder = TimeOfDay(
          hour: hour.clamp(0, 23),
          minute: minute.clamp(0, 59),
        );
      }
    });
  }

  Future<void> refreshStatus() async {
    final s = Map<String, dynamic>.from(await call('schoolStatus'));
    if (mounted) {
      if (s['location_permission'] != status['location_permission'] ||
          s['steps_permission'] != status['steps_permission']) {
        sensorPermissionsChanged = true;
      }
      setState(() => status = s);
    }
  }

  Future<void> refresh() async {
    if (refreshing) return;
    refreshing = true;
    try {
      await refreshStatus();
      if (!mounted) return;
      if (status['enrolled'] == true) {
        final cached = status['home'];
        if (cached is Map) applyHome(Map<String, dynamic>.from(cached));
        final h = Map<String, dynamic>.from(await call('schoolHome'));
        if (!mounted) return;
        applyHome(h); // Authorization must not depend on forms/history loading.
        await refreshStatus();
        final f = await call('schoolForms') as List;
        if (!mounted) return;
        setState(() {
          form = f.isEmpty ? null : Map<String, dynamic>.from(f.first);
          formsLoaded = true;
          formsUnavailable = false;
        });
        final r = Map<String, dynamic>.from(await call('schoolRequests'));
        List<dynamic> historyRows = [];
        try {
          final rawHistory = await call('schoolHistory');
          if (rawHistory is List) historyRows = rawHistory;
        } catch (_) {
          historyRows = responseHistory;
        }
        final rawLog = await call('schoolDeliveryLog');
        final log = rawLog is List ? rawLog : const [];
        final d = Map<String, dynamic>.from(await call('schoolDraft'));
        if (!mounted) return;
        setState(() {
          requests = r;
          responseHistory = historyRows;
          deliveryLog = log;
          if (d['version'] == form?['version']) {
            answers = Map<String, dynamic>.from(d['answers'] ?? {});
            functioning = d['functioning'];
          }
        });
      } else {
        setState(() {
          home = {};
          requests = {};
          deliveryLog = [];
          responseHistory = [];
          form = null;
          answers = {};
          functioning = null;
          preferencesDirty = false;
        });
      }
    } catch (_) {
      formsUnavailable = true;
      if (mounted) {
        setState(
          () => message =
              'No se pudo actualizar todo. Mostramos la última información guardada; revisa tu conexión.',
        );
      }
    } finally {
      refreshing = false;
      if (mounted) await ensureSensors();
    }
  }

  Future<void> action(String method, [Map<String, dynamic>? args]) async {
    if (busy) return;
    setState(() {
      busy = true;
      message = '';
    });
    try {
      final v = await call(method, args);
      if (v is Map && mounted) {
        setState(() {
          status = Map<String, dynamic>.from(v);
          if (method == 'schoolParticipation' &&
              status['policy_pending'] != true) {
            preferencesDirty = false;
          }
        });
      }
      if (mounted) {
        setState(
          () => message = (status['rejected'] ?? 0) > 0
              ? 'Hay un envío que no pudo aceptarse. Actualiza la información de participación o consulta al equipo.'
              : (status['outbox_pending'] ?? 0) > 0
              ? 'Guardado en este teléfono. Hay envíos pendientes: el equipo todavía no los recibió.'
              : 'Operación completada. No hay envíos pendientes.',
        );
      }
      final decisionState = status['decision_state'];
      await refresh();
      if (method == 'schoolParticipation' && mounted) {
        setState(
          () => message = decisionState == 'confirmed'
              ? 'Participación guardada.'
              : decisionState == 'rejected'
              ? 'No se pudo aceptar esta decisión. Revisa la información vigente y vuelve a intentarlo.'
              : 'Decisión guardada en el teléfono; pendiente de conexión. La pausa o retirada ya detiene la captura local.',
        );
        if (scroll.hasClients) {
          await scroll.animateTo(
            0,
            duration: const Duration(milliseconds: 250),
            curve: Curves.easeOut,
          );
        }
      }
    } on PlatformException catch (e) {
      if (mounted) {
        setState(
          () => message =
              e.message ??
              'No se pudo completar. Conservamos los envíos pendientes.',
        );
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> ensureSensors({bool reconfigure = false}) async {
    reconfigure = reconfigure || sensorPermissionsChanged;
    if (startingSensors ||
        status['active'] != true ||
        status['policy_pending'] == true ||
        status['reauth_required'] == true ||
        (status['sensor_running'] == true && !reconfigure)) {
      return;
    }
    final p = home['policy'] ?? {};
    final allowed =
        p['location'] == true &&
            [
              'precise',
              'approximate',
            ].contains(status['location_permission']) ||
        p['steps'] == true &&
            status['steps_supported'] == true &&
            status['steps_permission'] == true;
    if (!allowed) return;
    startingSensors = true;
    sensorPermissionsChanged = false;
    try {
      final result = await call('schoolStartSensors', {
        'reconfigure': reconfigure,
      });
      if (mounted && result is Map) {
        setState(() => status = Map<String, dynamic>.from(result));
      }
    } on PlatformException catch (e) {
      if (mounted) {
        setState(
          () => status['sensor_error'] =
              e.message ?? 'No se pudo iniciar la captura',
        );
      }
    } finally {
      startingSensors = false;
    }
  }

  Future<void> permission(String kind) async {
    if (busy || home['authorization']?['ready'] != true) return;
    final key = kind == 'background'
        ? 'location'
        : kind == 'notifications'
        ? 'reminders'
        : kind;
    if ((home['policy'] ?? {})[key] != true) {
      setState(() {
        if (key == 'usage') usage = true;
        if (key == 'location') location = true;
        if (key == 'steps') steps = true;
        if (key == 'reminders') reminders = true;
        preferencesDirty = true;
      });
      await decision('preferences');
    }
    if (!mounted ||
        status['policy_pending'] == true ||
        (home['policy'] ?? {})[key] != true) {
      if (mounted) {
        setState(
          () =>
              message = 'Pendiente de conexión. El permiso aún no se solicitó.',
        );
      }
      return;
    }
    setState(() {
      busy = true;
      message = '';
    });
    try {
      final result = await call('schoolPermission', {'kind': kind});
      await refreshStatus();
      await ensureSensors(
        reconfigure:
            result?['state'] == 'granted' &&
            (kind == 'location' || kind == 'steps'),
      );
      if (mounted) {
        setState(
          () => message = result?['state'] == 'denied'
              ? 'Permiso no concedido.'
              : '',
        );
      }
    } on PlatformException catch (e) {
      if (mounted) {
        setState(() => message = e.message ?? 'No se pudo abrir el permiso.');
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> startSensors() async {
    setState(() {
      busy = true;
      message = '';
    });
    try {
      final result = Map<String, dynamic>.from(
        await call('schoolStartSensors'),
      );
      if (!mounted) return;
      setState(() {
        status = result;
        message = result['sensor_running'] == true
            ? 'Servicio iniciado. Verás una notificación; los primeros datos pueden tardar en llegar.'
            : (result['sensor_error'] as String?)?.isNotEmpty == true
            ? result['sensor_error']
            : 'El servicio todavía no se inició. Revisa los permisos y vuelve a intentarlo.';
      });
    } on PlatformException catch (e) {
      if (mounted) {
        setState(
          () => message = e.message ?? 'No se pudieron iniciar los sensores.',
        );
      }
    } finally {
      if (mounted) {
        setState(() => busy = false);
        if (scroll.hasClients) {
          await scroll.animateTo(
            0,
            duration: const Duration(milliseconds: 250),
            curve: Curves.easeOut,
          );
        }
      }
    }
  }

  Future<void> decision(String act) async {
    await action('schoolParticipation', {
      'body': jsonEncode({
        'action': act,
        'document_version': home['authorization']['version'],
        'occurred_at': DateTime.now().toUtc().toIso8601String(),
        'usage': usage,
        'location': location,
        'steps': steps,
        'raw_location_upload': raw && location,
        'research_access': research,
        'reminders': reminders,
        'reminder_time':
            '${reminder.hour.toString().padLeft(2, '0')}:${reminder.minute.toString().padLeft(2, '0')}',
      }),
    });
  }

  Widget card(String title, List<Widget> children) => Card(
    color: Colors.white,
    margin: const EdgeInsets.only(bottom: 18),
    child: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 14),
          ...children,
        ],
      ),
    ),
  );
  Widget button(String title, VoidCallback? action, {bool secondary = false}) =>
      Padding(
        padding: const EdgeInsets.only(top: 12),
        child: secondary
            ? OutlinedButton(
                onPressed: busy ? null : action,
                child: Text(title),
              )
            : FilledButton(onPressed: busy ? null : action, child: Text(title)),
      );
  Widget toggle(
    String title,
    bool value,
    ValueChanged<bool> change, {
    String? subtitle,
  }) => SwitchListTile(
    contentPadding: EdgeInsets.zero,
    title: Text(title),
    subtitle: subtitle == null ? null : Text(subtitle),
    value: value,
    onChanged: busy
        ? null
        : (v) {
            setState(() => preferencesDirty = true);
            change(v);
          },
  );
  Widget permissionCard() {
    final p = home['policy'] ?? {};
    final canEdit = status['policy_pending'] != true;
    Widget row(
      String title,
      IconData icon,
      String kind,
      bool granted, {
      bool supported = true,
      String? hint,
    }) {
      final key = kind == 'background'
          ? 'location'
          : kind == 'notifications'
          ? 'reminders'
          : kind;
      final enabled = p[key] == true;
      final ready = enabled && granted;
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 10),
        child: Row(
          children: [
            Icon(
              ready ? Icons.check_circle : icon,
              color: ready ? Colors.teal : Colors.blueGrey,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(fontWeight: FontWeight.w600),
                  ),
                  Text(
                    !supported
                        ? 'No disponible en este teléfono'
                        : ready
                        ? 'Concedido'
                        : enabled
                        ? 'Pendiente'
                        : 'No activado',
                    style: TextStyle(
                      color: ready ? Colors.teal : Colors.blueGrey,
                    ),
                  ),
                  if (hint != null && !ready)
                    Text(hint, style: Theme.of(context).textTheme.bodySmall),
                ],
              ),
            ),
            if (!ready && supported)
              TextButton(
                onPressed: busy || !canEdit ? null : () => permission(kind),
                key: ValueKey('permission-$kind'),
                child: Text('Permitir', semanticsLabel: 'Permitir $title'),
              ),
          ],
        ),
      );
    }

    final loc = [
      'precise',
      'approximate',
    ].contains(status['location_permission']);
    return card('Permisos de este teléfono', [
      const Text('Opcionales. Tú eliges qué compartir.'),
      if (!canEdit) const Text('Esperando conexión para guardar tu elección.'),
      row(
        'Uso de pantalla',
        Icons.phone_android,
        'usage',
        status['usage_access'] == 'available',
        hint: 'Sin mensajes ni contenido.',
      ),
      row('Ubicación', Icons.location_on_outlined, 'location', loc),
      if (p['location'] == true && loc)
        row(
          'Ubicación en segundo plano',
          Icons.my_location,
          'background',
          status['background_location'] == true,
        ),
      row(
        'Pasos',
        Icons.directions_walk,
        'steps',
        status['steps_permission'] == true,
        supported: status['steps_supported'] == true,
      ),
      row(
        'Notificaciones',
        Icons.notifications_outlined,
        'notifications',
        status['notifications_permission'] == true,
      ),
      const Divider(),
      Text(
        home['capture_active'] != true
            ? 'Participación pausada'
            : status['sensor_running'] == true
            ? 'Sensores activos'
            : 'Los sensores se iniciarán al conceder permisos.',
      ),
      button(
        home['capture_active'] == true ? 'Pausar' : 'Reanudar',
        () => decision(home['capture_active'] == true ? 'pause' : 'resume'),
        secondary: true,
      ),
      if ((status['sensor_error'] ?? '').toString().isNotEmpty) ...[
        Text(status['sensor_error']),
        button('Reintentar inicio', startSensors, secondary: true),
      ],
    ]);
  }

  Widget coverage() {
    final c = home['coverage'] ?? {};
    return card('Tu equipo y recursos de apoyo', [
      Text(c['text'] ?? 'Consulta a tu institución sus horarios de atención.'),
      const SizedBox(height: 8),
      Text(
        c['open'] == true
            ? 'El horario configurado está abierto.'
            : 'Fuera del horario configurado o sin confirmación actual.',
      ),
      const Text(
        'La aplicación no garantiza atención inmediata ni atención las 24 horas.',
      ),
      for (final r in c['resources'] ?? [])
        Padding(
          padding: const EdgeInsets.only(top: 12),
          child: Text('${r['title']}\n${r['contact']}'),
        ),
      const SizedBox(height: 8),
      const Text(
        'Sin conexión, estos son los últimos recursos guardados en el teléfono.',
      ),
    ]);
  }

  Future<void> saveDraft() async {
    await call('schoolDraft', {
      'value': jsonEncode({
        'version': form?['version'],
        'answers': answers,
        'functioning': functioning,
      }),
    });
  }

  @override
  Widget build(BuildContext context) {
    final enrolled = status['enrolled'] == true;
    final auth = home['authorization'] ?? {};
    return Scaffold(
      appBar: AppBar(
        title: const Text('Acompaña Escolar'),
        actions: [
          IconButton(
            onPressed: busy ? null : () => action('schoolSync'),
            tooltip: 'Sincronizar',
            icon: const Icon(Icons.sync),
          ),
        ],
      ),
      bottomNavigationBar: enrolled
          ? NavigationBar(
              selectedIndex: tab,
              onDestinationSelected: (i) {
                setState(() => tab = i);
                refresh();
              },
              destinations: const [
                NavigationDestination(
                  icon: Icon(Icons.home_outlined),
                  label: 'Inicio',
                ),
                NavigationDestination(
                  icon: Icon(Icons.assignment_outlined),
                  label: 'Cuestionario',
                ),
                NavigationDestination(
                  icon: Icon(Icons.chat_bubble_outline),
                  label: 'Solicitudes',
                ),
                NavigationDestination(
                  icon: Icon(Icons.shield_outlined),
                  label: 'Participación',
                ),
              ],
            )
          : null,
      body: SafeArea(
        child: ListView(
          controller: scroll,
          padding: const EdgeInsets.all(18),
          children: [
            if (busy) const LinearProgressIndicator(),
            if (message.isNotEmpty)
              Semantics(
                liveRegion: true,
                child: Container(
                  padding: const EdgeInsets.all(14),
                  margin: const EdgeInsets.only(bottom: 16),
                  color: const Color(0xffe3f2f0),
                  child: Text(message),
                ),
              ),
            if (status['reauth_required'] == true)
              card('Tu acceso necesita renovarse', [
                const Text(
                  'Pide una nueva invitación a la institución. Para usarla se borrarán los borradores y envíos que queden en este teléfono.',
                ),
                button(
                  'Borrar datos locales y usar nueva invitación',
                  () => action('schoolForget'),
                ),
              ]),
            if (home['is_test'] == true)
              const Padding(
                padding: EdgeInsets.only(bottom: 12),
                child: Text('Cuenta de prueba · identidad ficticia'),
              ),
            if (!enrolled) ...[
              card('Un espacio para acompañarte', const [
                Icon(Icons.favorite_border, size: 54, color: Color(0xff137c84)),
                SizedBox(height: 18),
                Text(
                  'Revisa tus actividades y solicita conversar con el equipo de tu institución. Tú decides qué información opcional compartir.',
                ),
              ]),
              card('Ingresa con tu invitación', [
                TextField(
                  controller: server,
                  keyboardType: TextInputType.url,
                  decoration: const InputDecoration(
                    labelText: 'Dirección HTTPS de la institución',
                  ),
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: invitation,
                  autocorrect: false,
                  decoration: const InputDecoration(
                    labelText: 'Invitación personal',
                  ),
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: code,
                  keyboardType: TextInputType.number,
                  autocorrect: false,
                  decoration: const InputDecoration(
                    labelText: 'Código recibido por separado',
                  ),
                ),
                button(
                  'Vincular mi teléfono',
                  () => action('schoolEnroll', {
                    'server': server.text.trim(),
                    'invitation': invitation.text.trim(),
                    'code': code.text.trim(),
                  }),
                ),
              ]),
            ] else if (tab == 0) ...[
              card('Hola, ${home['name'] ?? 'bienvenido'}', [
                Text(
                  auth['ready'] == true
                      ? 'Tu espacio de acompañamiento está disponible.'
                      : 'Completa la información de participación para habilitar el cuestionario.',
                ),
                if (home['pilot_enabled'] == false)
                  const Text(
                    'La institución aún no habilitó el piloto. No se recogen datos reales.',
                  ),
                button(
                  'Quiero que me contacten',
                  () => action('schoolSupport'),
                  secondary: true,
                ),
                button(
                  'Revisar mi participación',
                  () => setState(() => tab = 3),
                  secondary: true,
                ),
                const SizedBox(height: 12),
                Text('Envíos pendientes: ${status['outbox_pending'] ?? 0}'),
                Text(
                  'Última sincronización: ${status['last_sync'] == '' ? 'Todavía no disponible' : status['last_sync'] ?? 'Todavía no disponible'}',
                ),
              ]),
              coverage(),
            ] else if (tab == 1) ...[
              if (form == null)
                card(
                  !formsLoaded
                      ? (formsUnavailable
                            ? 'Sin conexión'
                            : 'Consultando cuestionario…')
                      : 'No hay cuestionario pendiente',
                  [
                    Text(
                      auth['ready'] != true
                          ? 'Primero completa tu participación.'
                          : (status['outbox_pending'] ?? 0) > 0
                          ? 'Tu respuesta puede estar esperando conexión. Sincroniza para confirmar su recepción.'
                          : 'Aparecerá aquí automáticamente.',
                    ),
                    button(
                      'Solicitar contacto',
                      () => action('schoolSupport'),
                      secondary: true,
                    ),
                  ],
                )
              else
                card('Cómo te has sentido', [
                  Text(form!['title'] ?? 'Cuestionario PHQ-9'),
                  Text(
                    form!['recall'] ??
                        form!['instructions'] ??
                        'Durante las últimas 2 semanas, ¿qué tan seguido ha tenido molestias debido a los siguientes problemas?',
                  ),
                  for (final q in form!['questions'])
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      child: RadioGroup<int>(
                        groupValue: answers[q['id']],
                        onChanged: (v) {
                          if (busy) return;
                          setState(() => answers[q['id']] = v);
                          saveDraft();
                        },
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            Text(
                              q['text'],
                              style: const TextStyle(
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            for (final o in form!['options'])
                              RadioListTile<int>(
                                contentPadding: EdgeInsets.zero,
                                value: o['value'],
                                title: Text(o['label']),
                              ),
                          ],
                        ),
                      ),
                    ),
                  if (answers.values.any((v) => v > 0)) ...[
                    Text(form!['functioning']['text']),
                    RadioGroup<int>(
                      groupValue: functioning,
                      onChanged: (v) {
                        if (busy) return;
                        setState(() => functioning = v);
                        saveDraft();
                      },
                      child: Column(
                        children: [
                          for (final o
                              in (form!['functioning']['options'] as List)
                                  .asMap()
                                  .entries)
                            RadioListTile<int>(
                              contentPadding: EdgeInsets.zero,
                              value: o.key,
                              title: Text(o.value),
                            ),
                        ],
                      ),
                    ),
                  ],
                  const Text(
                    'Tu borrador se guarda cifrado en este teléfono. Solo se envía cuando eliges enviar.',
                  ),
                  button(
                    'Enviar respuesta',
                    answers.length == 9 &&
                            (!answers.values.any((v) => v > 0) ||
                                functioning != null)
                        ? () async {
                            final now = DateTime.now().toUtc();
                            await action('schoolSubmit', {
                              'body': jsonEncode({
                                'instrument_code': form!['instrument_id'],
                                'instrument_version': form!['version'],
                                'answers': answers,
                                'functioning': functioning,
                                'applied_at': now.toIso8601String(),
                                'recall_start': now
                                    .subtract(const Duration(days: 14))
                                    .toIso8601String(),
                                'recall_end': now.toIso8601String(),
                              }),
                            });
                          }
                        : null,
                  ),
                ]),
              coverage(),
              historyCard(),
            ] else if (tab == 2) ...[
              card('Mis solicitudes', [
                const Text(
                  'El equipo confirma y organiza el contacto desde su bandeja. Una solicitud recibida no significa que alguien ya la haya revisado.',
                ),
                button(
                  'Quiero que me contacten',
                  () => action('schoolSupport'),
                ),
                for (final r in requests['requests'] ?? [])
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Solicitud de acompañamiento'),
                    subtitle: Text('${r['state']}'),
                  ),
              ]),
              if (deliveryLog.isNotEmpty)
                card('Estado de mis envíos', [
                  const Text(
                    'Tus respuestas y solicitudes se guardan cifradas en el teléfono hasta que el equipo las recibe. Nada se marca como recibido por caducar.',
                  ),
                  for (final item in deliveryLog)
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      title: Text('${item['label']}'),
                      subtitle: Text(
                        item['state'] == 'pending'
                            ? 'Pendiente de envío — el equipo aún no lo recibió'
                            : item['state'] == 'rejected'
                            ? 'No se pudo registrar${(item['error'] ?? '').toString().contains('409') ? ': ya había una respuesta para ese período' : ''}. Puedes descartarlo o pedir apoyo.'
                            : 'Datos de sensores caducados sin enviar. No afecta a tus cuestionarios ni solicitudes.',
                        style: TextStyle(
                          color: item['state'] == 'rejected'
                              ? Theme.of(context).colorScheme.error
                              : null,
                        ),
                      ),
                      trailing: item['dismissible'] == true
                          ? TextButton(
                              onPressed: busy
                                  ? null
                                  : () => action('schoolDismiss', {
                                      'id': item['id'],
                                    }),
                              child: const Text('Descartar'),
                            )
                          : null,
                    ),
                ]),
              card('Mis citas', [
                if ((requests['appointments'] ?? []).isEmpty)
                  const Text('Todavía no tienes citas programadas.'),
                for (final a in requests['appointments'] ?? [])
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Text('${a['date']} · ${a['place'] ?? ''}'),
                      Text('${a['state']}'),
                      if (a['state'] == 'pending')
                        button(
                          'Confirmar asistencia',
                          () => action('schoolConfirm', {'id': a['id']}),
                        ),
                    ],
                  ),
              ]),
              coverage(),
            ] else ...[
              if (auth['ready'] == true) permissionCard(),
              if (auth['ready'] == true)
                Card(
                  child: ExpansionTile(
                    title: const Text('Mi participación y preferencias'),
                    children: [participationOptions(auth)],
                  ),
                )
              else
                participationOptions(auth),
            ],
          ],
        ),
      ),
    );
  }

  Widget participationOptions(dynamic auth) => Column(
    children: [
      card('Tú decides', [
        if (auth['ready'] != true) Text(home['purpose'] ?? ''),
        const SizedBox(height: 12),
        Text(
          home['document'] ??
              'Actualiza para leer la información de participación.',
        ),
        if (auth['minor'] == true && auth['guardian'] != true)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 16),
            child: Text(
              'Falta la autorización de tu responsable. Se actualizará automáticamente.',
            ),
          ),
        if (auth['student'] != true && auth['guardian'] == true)
          CheckboxListTile(
            contentPadding: EdgeInsets.zero,
            value: accepted,
            onChanged: (v) => setState(() => accepted = v ?? false),
            title: const Text(
              'He leído la información y acepto participar voluntariamente.',
            ),
          ),
        if (auth['ready'] == true) ...[
          toggle(
            'Uso del dispositivo',
            usage,
            (v) => setState(() => usage = v),
            subtitle:
                'Eventos de pantalla. No se leen mensajes, llamadas ni contenidos.',
          ),
          toggle(
            'Ubicación',
            location,
            (v) => setState(() {
              location = v;
              if (!v) raw = false;
            }),
            subtitle:
                'Puedes compartir resúmenes de movilidad calculados en tu teléfono.',
          ),
          toggle(
            'Pasos con el teléfono',
            steps,
            (v) => setState(() => steps = v),
            subtitle:
                'Requiere un sensor compatible; no mide toda tu actividad física.',
          ),
          if (location)
            toggle(
              'Enviar coordenadas al servidor',
              raw,
              (v) => setState(() => raw = v),
              subtitle:
                  'Opcional. Si lo desactivas, las coordenadas permanecen en este teléfono.',
            ),
          if (location) ...[
            button(
              'Usar mi ubicación como zona habitual',
              () => action('schoolHomeZone', {'clear': false}),
              secondary: true,
            ),
            button(
              'Eliminar zona habitual',
              () => action('schoolHomeZone', {'clear': true}),
              secondary: true,
            ),
          ],
          toggle(
            'Autorizar análisis de investigación',
            research,
            (v) => setState(() => research = v),
          ),
          toggle(
            'Recibir recordatorios',
            reminders,
            (v) => setState(() => reminders = v),
          ),
          if (reminders)
            TextButton(
              onPressed: () async {
                final t = await showTimePicker(
                  context: context,
                  initialTime: reminder,
                );
                if (t != null) {
                  setState(() {
                    reminder = t;
                    preferencesDirty = true;
                  });
                }
              },
              child: Text('Horario preferido: ${reminder.format(context)}'),
            ),
        ],
        button(
          auth['minor'] == true && auth['guardian'] != true
              ? 'Pendiente de autorización del responsable'
              : auth['student'] == true
              ? 'Guardar mis preferencias'
              : 'Aceptar y continuar',
          auth['student'] == true || accepted && auth['guardian'] == true
              ? () => decision(
                  auth['student'] == true
                      ? 'preferences'
                      : auth['minor'] == true
                      ? 'assent'
                      : 'consent',
                )
              : null,
        ),
      ]),
      card('Retirar mi participación', [
        const Text(
          'Se detiene la captura y se solicita borrar los datos. Si no hay conexión, el retiro queda pendiente y la captura se detiene aquí de inmediato.',
        ),
        button('Retirarme', () async {
          final yes = await showDialog<bool>(
            context: context,
            builder: (c) => AlertDialog(
              title: const Text('¿Retirar tu participación?'),
              content: const Text(
                'Se solicitará borrar tus datos del sistema.',
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(c, false),
                  child: const Text('Cancelar'),
                ),
                FilledButton(
                  onPressed: () => Navigator.pop(c, true),
                  child: const Text('Retirarme'),
                ),
              ],
            ),
          );
          if (yes == true) await decision('withdraw');
        }, secondary: true),
      ]),
    ],
  );
}
