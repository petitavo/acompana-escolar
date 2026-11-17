import 'dart:convert';
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'permissions.dart';

const brandColor = Color(0xff137c84);

class SchoolApp extends StatelessWidget {
  const SchoolApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Acompaña Escolar',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(seedColor: brandColor),
      scaffoldBackgroundColor: const Color(0xfff4f7fb),
      cardTheme: CardThemeData(
        color: Colors.white,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(18),
          side: const BorderSide(color: Color(0xffdfe7ee)),
        ),
      ),
      inputDecorationTheme: const InputDecorationTheme(
        border: OutlineInputBorder(),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(50)),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(minimumSize: const Size.fromHeight(48)),
      ),
    ),
    home: const SchoolHome(),
  );
}

/// Fecha legible en español a partir de ISO-8601 (sin depender de paquetes externos).
String friendlyDate(dynamic value, {bool time = true}) {
  if (value == null || value.toString().isEmpty) return 'Todavía no disponible';
  final parsed = DateTime.tryParse(value.toString());
  if (parsed == null) return value.toString();
  final d = parsed.toLocal();
  const months = [
    'ene',
    'feb',
    'mar',
    'abr',
    'may',
    'jun',
    'jul',
    'ago',
    'sep',
    'oct',
    'nov',
    'dic',
  ];
  final date = '${d.day} ${months[d.month - 1]} ${d.year}';
  if (!time) return date;
  return '$date, ${d.hour.toString().padLeft(2, '0')}:${d.minute.toString().padLeft(2, '0')}';
}

/// Primer número telefónico de un texto (113, 0800-10828, +51 1 2345678…).
String? phoneIn(String text) {
  final m = RegExp(r'\+?\d[\d\s-]{1,14}\d').firstMatch(text);
  return m?.group(0)?.replaceAll(RegExp(r'[\s-]'), '');
}

const requestStates = {
  'new': 'Recibida, el equipo aún no la revisa',
  'acknowledged': 'El equipo ya la vio',
  'contact_planned': 'El equipo coordinará un contacto contigo',
  'in_followup': 'En seguimiento',
  'closed': 'Cerrada',
};
const appointmentStates = {
  'pending': 'Por confirmar',
  'confirmed': 'Confirmada',
  'completed': 'Realizada',
  'cancelled': 'Cancelada',
};

/// Acepta la invitación sola o el enlace completo que entrega el colegio
/// (https://colegio/app?inv=TOKEN). Devuelve servidor y token.
({String server, String token}) parseInvitation(String text, String server) {
  final value = text.trim();
  final uri = Uri.tryParse(value);
  if (uri != null && uri.hasScheme && uri.host.isNotEmpty) {
    final token =
        uri.queryParameters['inv'] ??
        uri.queryParameters['invitation'] ??
        uri.queryParameters['token'] ??
        '';
    if (token.isNotEmpty) {
      return (server: '${uri.scheme}://${uri.authority}', token: token);
    }
  }
  return (server: server.trim(), token: value);
}

class SchoolHome extends StatefulWidget {
  const SchoolHome({super.key});
  @override
  State<SchoolHome> createState() => _SchoolHomeState();
}

class _SchoolHomeState extends State<SchoolHome> with WidgetsBindingObserver {
  static const bridge = MethodChannel('pe.upc.acompana/collector');
  static const compiledServer = String.fromEnvironment('API_URL');
  Map<String, dynamic> status = {}, home = {}, requests = {}, answers = {};
  Map<String, dynamic> device = {};
  List<dynamic> deliveryLog = [], responseHistory = [];
  Map<String, dynamic>? form;
  final server = TextEditingController(text: compiledServer);
  final invitation = TextEditingController(), code = TextEditingController();
  final scroll = ScrollController();
  int tab = 0;
  int? functioning;
  bool busy = false,
      accepted = false,
      refreshing = false,
      preferencesDirty = false,
      editServer = compiledServer.isEmpty;
  String message = '';
  Timer? refreshTimer;
  bool startingSensors = false, formsLoaded = false, formsUnavailable = false;
  bool sensorPermissionsChanged = false, guideOpen = false;
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
                    'Corrige el mismo período. Guardamos la respuesta anterior y lo que el equipo ya revisó.',
                  ),
                  for (final q in definition['questions']) ...[
                    const SizedBox(height: 10),
                    Text(q['text']),
                    DropdownButtonFormField<int>(
                      initialValue: corrected[q['id']],
                      isExpanded: true,
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
                  const SizedBox(height: 10),
                  Text(definition['functioning']['text']),
                  DropdownButtonFormField<int>(
                    initialValue: impact,
                    isExpanded: true,
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

  Widget historyCard() => card('Mis respuestas', [
    const Text(
      'Aquí ves los cuestionarios que el equipo ya recibió. Si te equivocaste, puedes corregirlos.',
    ),
    if (responseHistory.isEmpty)
      const Padding(
        padding: EdgeInsets.only(top: 8),
        child: Text('Todavía no hay respuestas recibidas.'),
      ),
    for (final raw in responseHistory)
      Builder(
        builder: (context) {
          final row = Map<String, dynamic>.from(raw);
          final def = row['definition'];
          return ExpansionTile(
            tilePadding: EdgeInsets.zero,
            title: Text(friendlyDate(row['applied_at'], time: false)),
            subtitle: Text(
              row['current'] == true
                  ? 'Recibida${(row['revision'] ?? 1) > 1 ? ' · corregida' : ''}'
                  : 'Versión anterior (se conserva)',
            ),
            children: [
              for (final q in def['questions'])
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(q['text']),
                  subtitle: Text(
                    '${(def['options'] as List).firstWhere((o) => o['value'] == row['answers'][q['id']], orElse: () => {'label': '—'})['label']}',
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

  Future<Map<String, dynamic>> refreshStatus() async {
    final s = Map<String, dynamic>.from(await call('schoolStatus'));
    if (mounted) {
      if (s['location_permission'] != status['location_permission'] ||
          s['steps_permission'] != status['steps_permission']) {
        sensorPermissionsChanged = true;
      }
      setState(() => status = s);
    }
    return s;
  }

  Future<Map<String, dynamic>> refreshDevice() async {
    try {
      final d = await call('schoolDeviceSetup');
      if (d is Map && mounted) {
        setState(() => device = Map<String, dynamic>.from(d));
      }
    } catch (_) {
      // Versiones anteriores del puente nativo: la guía funciona sin datos de marca.
    }
    return device;
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
        await refreshDevice();
        final f = await call('schoolForms') as List;
        if (!mounted) return;
        setState(() {
          final next = f.isEmpty ? null : Map<String, dynamic>.from(f.first);
          if (next?['instrument_id'] != form?['instrument_id']) {
            answers = {};
            functioning = null;
          }
          form = next;
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
          if (d['version'] == form?['version'] &&
              (d['instrument'] == null ||
                  d['instrument'] == form?['instrument_id'])) {
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
              'No pudimos actualizar todo. Te mostramos lo último guardado; revisa tu conexión a internet.',
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
    final firstConsent =
        method == 'schoolParticipation' &&
        home['authorization']?['student'] != true;
    var openGuideAfter = false;
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
              ? 'Hay un envío que no pudo aceptarse. Revisa "Estado de mis envíos" en Solicitudes o pide ayuda al equipo.'
              : (status['outbox_pending'] ?? 0) > 0
              ? 'Guardado en este teléfono. Se enviará solo cuando haya internet (el equipo todavía no los recibió).'
              : method == 'schoolSupport'
              ? 'Listo, tu solicitud llegó al equipo. Te contactarán en su horario de atención.'
              : method == 'schoolSubmit'
              ? '¡Gracias! Tu respuesta llegó al equipo.'
              : 'Listo, todo está enviado.',
        );
      }
      final decisionState = status['decision_state'];
      await refresh();
      if (method == 'schoolParticipation' && mounted) {
        setState(
          () => message = decisionState == 'confirmed'
              ? 'Participación guardada.'
              : decisionState == 'rejected'
              ? 'No se pudo guardar esta decisión. Actualiza la pantalla e inténtalo otra vez.'
              : 'Tu decisión se guardó en el teléfono y se enviará al tener internet. Si pausaste o te retiraste, la captura ya se detuvo.',
        );
        if (scroll.hasClients) {
          await scroll.animateTo(
            0,
            duration: const Duration(milliseconds: 250),
            curve: Curves.easeOut,
          );
        }
        // Después de aceptar por primera vez, la guía de permisos se abre sola
        // (más abajo, cuando busy ya es falso; si no, la guía no puede pedir nada).
        openGuideAfter =
            firstConsent &&
            decisionState == 'confirmed' &&
            home['authorization']?['ready'] == true;
      }
    } on PlatformException catch (e) {
      if (mounted) {
        setState(
          () => message =
              e.message ??
              'No se pudo completar. Lo que estaba pendiente sigue guardado.',
        );
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
    if (openGuideAfter && mounted) await openGuide();
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

  String preferenceFor(String kind) => kind == 'background'
      ? 'location'
      : kind == 'notifications'
      ? 'reminders'
      : kind;

  /// Pide un permiso o ajuste. Si el permiso depende de una preferencia de participación que
  /// aún no está activa, primero la guarda (un solo toque para el alumno). Devuelve el
  /// resultado de Android: granted, denied, blocked, approximate, settings_opened…
  Future<String?> permission(String kind) async {
    if (busy || home['authorization']?['ready'] != true) return null;
    if (kind == 'battery' || kind == 'autostart' || kind == 'settings') {
      try {
        final result = await call(
          kind == 'battery'
              ? 'schoolOpenBattery'
              : kind == 'autostart'
              ? 'schoolOpenAutostart'
              : 'schoolOpenSettings',
        );
        return result is Map ? result['state'] : null;
      } on PlatformException catch (e) {
        if (mounted) setState(() => message = e.message ?? '');
        return 'unavailable';
      } on MissingPluginException {
        return 'unavailable';
      }
    }
    final key = preferenceFor(kind);
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
          () => message =
              'Tu elección se guardó, pero falta internet para confirmarla. El permiso se pedirá cuando vuelva la conexión.',
        );
      }
      return 'offline';
    }
    setState(() {
      busy = true;
      message = '';
    });
    String? state;
    try {
      final result = await call('schoolPermission', {'kind': kind});
      state = result is Map ? result['state'] : null;
      await refreshStatus();
      await ensureSensors(
        reconfigure:
            (state == 'granted' || state == 'approximate') &&
            (kind == 'location' || kind == 'steps'),
      );
      if (mounted) {
        setState(
          () => message = state == 'denied'
              ? 'Permiso no concedido. Puedes intentarlo otra vez cuando quieras.'
              : state == 'blocked'
              ? 'Android ya no muestra la ventana de este permiso. Actívalo desde "Abrir ajustes".'
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
    return state;
  }

  Future<void> openGuide({String? initialKind}) async {
    if (guideOpen || home['authorization']?['ready'] != true) return;
    guideOpen = true;
    try {
      await Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => PermissionGuide(
            initialKind: initialKind,
            loadStatus: refreshStatus,
            loadDevice: refreshDevice,
            policy: () => home['policy'] ?? {},
            request: permission,
            confirm: (key) async {
              try {
                await call('schoolSetupConfirm', {'key': key, 'value': true});
              } catch (_) {}
            },
          ),
        ),
      );
    } finally {
      guideOpen = false;
    }
    if (mounted) await refresh();
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
            ? 'Listo. Verás una notificación fija mientras se recogen datos.'
            : (result['sensor_error'] as String?)?.isNotEmpty == true
            ? result['sensor_error']
            : 'Todavía no se pudo iniciar. Revisa los permisos y vuelve a intentarlo.';
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

  bool get supportOpen => (requests['requests'] ?? []).any(
    (r) => r is Map && r['state'] != 'closed',
  );

  Future<void> requestSupport() async {
    if (supportOpen) {
      setState(
        () => message =
            'Ya tienes una solicitud abierta. El equipo te contactará; puedes ver su estado en Solicitudes.',
      );
      return;
    }
    final yes = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('¿Quieres que el equipo te contacte?'),
        content: const Text(
          'El equipo de psicología de tu colegio recibirá tu pedido y te buscará en su horario de atención. No necesitas explicar el motivo.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(c, false),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(c, true),
            child: const Text('Sí, que me contacten'),
          ),
        ],
      ),
    );
    if (yes == true) await action('schoolSupport');
  }

  /// Abre el marcador del teléfono con el número (no llama solo).
  Future<void> dial(String number) async {
    try {
      await call('schoolDial', {'number': number});
    } catch (_) {
      if (mounted) setState(() => message = 'Marca $number desde tu teléfono.');
    }
  }

  Widget resourceLine(Map r) {
    final number = phoneIn('${r['contact'] ?? ''}');
    return Padding(
      padding: const EdgeInsets.only(top: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.call_outlined, size: 20, color: brandColor),
          const SizedBox(width: 10),
          Expanded(child: Text('${r['title']}\n${r['contact']}')),
          if (number != null)
            TextButton(
              onPressed: () => dial(number),
              child: Text('Llamar', semanticsLabel: 'Llamar al $number'),
            ),
        ],
      ),
    );
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

  Widget card(String title, List<Widget> children, {Widget? leading}) => Card(
    margin: const EdgeInsets.only(bottom: 16),
    child: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              if (leading != null) ...[leading, const SizedBox(width: 12)],
              Expanded(
                child: Text(
                  title,
                  style: Theme.of(context).textTheme.titleLarge,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
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

  List<SetupStep> get steps_ => setupSteps(status, device);
  int get readySteps => steps_
      .where((s) => stepState(s, status, device, home['policy'] ?? {}) == 'ready')
      .length;

  Widget permissionCard() {
    final p = home['policy'] ?? {};
    final canEdit = status['policy_pending'] != true;
    final list = steps_;
    return card('Permisos de este teléfono', [
      Text(
        'Todos son opcionales. $readySteps de ${list.length} activos.',
      ),
      if (!canEdit)
        const Padding(
          padding: EdgeInsets.only(top: 6),
          child: Text('Esperando internet para guardar tu elección.'),
        ),
      for (final s in list)
        Builder(
          builder: (context) {
            final state = stepState(s, status, device, p);
            final ready = state == 'ready';
            final unsupported = s.kind == 'steps' && status['steps_supported'] == false;
            return ListTile(
              contentPadding: EdgeInsets.zero,
              leading: Icon(
                ready ? Icons.check_circle : s.icon,
                color: stateColor(context, state),
              ),
              title: Text(s.title),
              subtitle: Text(
                unsupported
                    ? 'No disponible en este teléfono'
                    : ready
                    ? 'Activo'
                    : stateLabels[state] ?? state,
                style: TextStyle(color: stateColor(context, state)),
              ),
              onTap: busy || !canEdit
                  ? null
                  : () => openGuide(initialKind: s.kind),
              trailing: ready || unsupported
                  ? null
                  : TextButton(
                      key: ValueKey('permission-${s.kind}'),
                      onPressed: busy || !canEdit
                          ? null
                          : s.kind == 'battery' || s.kind == 'autostart'
                          ? () => openGuide(initialKind: s.kind)
                          : () => permission(s.kind),
                      child: Text(
                        state == 'approximate'
                            ? 'Usar precisa'
                            : s.kind == 'background' && state == 'pending'
                            ? 'Ajustes'
                            : state == 'off'
                            ? 'Activar'
                            : 'Permitir',
                        semanticsLabel: 'Permitir ${s.title}',
                      ),
                    ),
            );
          },
        ),
      button(
        'Abrir guía paso a paso',
        canEdit ? () => openGuide() : null,
        secondary: true,
      ),
      const Divider(height: 32),
      Row(
        children: [
          Icon(
            home['capture_active'] != true
                ? Icons.pause_circle_outline
                : status['sensor_running'] == true
                ? Icons.sensors
                : Icons.hourglass_empty,
            color: brandColor,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              home['capture_active'] != true
                  ? 'Participación pausada'
                  : status['sensor_running'] == true
                  ? 'Sensores activos'
                  : 'Los sensores se iniciarán al conceder ubicación o pasos.',
            ),
          ),
        ],
      ),
      button(
        home['capture_active'] == true ? 'Pausar' : 'Reanudar',
        () => decision(home['capture_active'] == true ? 'pause' : 'resume'),
        secondary: true,
      ),
      if ((status['sensor_error'] ?? '').toString().isNotEmpty) ...[
        const SizedBox(height: 10),
        Text(status['sensor_error']),
        button('Reintentar inicio', startSensors, secondary: true),
      ],
    ]);
  }

  Widget coverage() {
    final c = home['coverage'] ?? {};
    return card(
      'Tu equipo y recursos de apoyo',
      [
        Text(c['text'] ?? 'Consulta a tu colegio sus horarios de atención.'),
        const SizedBox(height: 8),
        Text(
          c['open'] == true
              ? 'Ahora el equipo está en horario de atención.'
              : 'Ahora el equipo está fuera de su horario de atención.',
          style: const TextStyle(fontWeight: FontWeight.w600),
        ),
        const Text(
          'La app no reemplaza una atención de emergencia ni atiende las 24 horas.',
        ),
        for (final r in c['resources'] ?? []) resourceLine(r),
      ],
      leading: const Icon(Icons.support_agent, color: brandColor),
    );
  }

  Future<void> saveDraft() async {
    await call('schoolDraft', {
      'value': jsonEncode({
        'version': form?['version'],
        'instrument': form?['instrument_id'],
        'answers': answers,
        'functioning': functioning,
      }),
    });
  }

  bool get isPhq => form?['functioning'] != null;
  List optionsFor(dynamic q) => (q['options'] ?? form!['options']) as List;

  Future<void> submitForm() async {
    final now = DateTime.now().toUtc();
    final recallDays = (form!['recall_days'] ?? 14) as int;
    final safety = isPhq && (answers['q9'] ?? 0) > 0;
    await action('schoolSubmit', {
      'path': form!['submit_path'] ?? '/me/questionnaires',
      'body': jsonEncode({
        'instrument_code': form!['instrument_id'],
        'instrument_version': form!['version'],
        'answers': answers,
        if (isPhq) 'functioning': functioning,
        'applied_at': now.toIso8601String(),
        'recall_start': now.subtract(Duration(days: recallDays)).toIso8601String(),
        'recall_end': now.toIso8601String(),
      }),
    });
    if (safety && mounted) {
      final c = home['coverage'] ?? {};
      await showDialog<void>(
        context: context,
        builder: (dialog) => AlertDialog(
          title: const Text('Gracias por contarlo'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Una persona del equipo de psicología revisará tu respuesta. Si sientes que podrías hacerte daño ahora mismo, no esperes: busca a un adulto de confianza o comunícate con:',
                ),
                for (final r in c['resources'] ?? []) resourceLine(r),
              ],
            ),
          ),
          actions: [
            FilledButton(
              onPressed: () => Navigator.pop(dialog),
              child: const Text('Entendido'),
            ),
          ],
        ),
      );
    }
  }

  Widget questionnaire() {
    final questions = form!['questions'] as List;
    final done = questions.where((q) => answers[q['id']] != null).length;
    final needsFunctioning = isPhq && answers.values.any((v) => v > 0);
    final complete =
        done == questions.length && (!needsFunctioning || functioning != null);
    return card(isPhq ? 'Cómo te has sentido' : (form!['title'] ?? 'Pregunta breve'), [
      Text(
        form!['recall'] ??
            form!['instructions'] ??
            'Durante las últimas 2 semanas, ¿qué tan seguido ha tenido molestias debido a los siguientes problemas?',
        style: const TextStyle(fontWeight: FontWeight.w600),
      ),
      const SizedBox(height: 6),
      const Text(
        'No hay respuestas buenas ni malas. Solo el equipo de psicología verá lo que respondas.',
      ),
      const SizedBox(height: 10),
      LinearProgressIndicator(value: questions.isEmpty ? 0 : done / questions.length),
      Padding(
        padding: const EdgeInsets.only(top: 4),
        child: Text('$done de ${questions.length} respondidas'),
      ),
      for (final (i, q) in questions.indexed)
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 12),
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
                  questions.length > 1 ? '${i + 1}. ${q['text']}' : q['text'],
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
                for (final o in optionsFor(q))
                  RadioListTile<int>(
                    contentPadding: EdgeInsets.zero,
                    dense: true,
                    value: o['value'],
                    title: Text(o['label']),
                  ),
              ],
            ),
          ),
        ),
      if (needsFunctioning) ...[
        Text(
          form!['functioning']['text'],
          style: const TextStyle(fontWeight: FontWeight.w600),
        ),
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
                  in (form!['functioning']['options'] as List).asMap().entries)
                RadioListTile<int>(
                  contentPadding: EdgeInsets.zero,
                  dense: true,
                  value: o.key,
                  title: Text(o.value),
                ),
            ],
          ),
        ),
      ],
      const Text(
        'Tus respuestas se guardan cifradas en este teléfono mientras respondes. Solo se envían cuando tocas "Enviar respuesta".',
      ),
      button('Enviar respuesta', complete ? submitForm : null),
    ]);
  }

  Widget setupCard() {
    final list = steps_;
    final ready = readySteps;
    return card(
      ready == list.length ? 'Tu teléfono está listo' : 'Prepara tu teléfono',
      [
        LinearProgressIndicator(value: list.isEmpty ? 0 : ready / list.length),
        const SizedBox(height: 8),
        Text(
          ready == list.length
              ? 'Todos los permisos que elegiste están activos.'
              : '$ready de ${list.length} pasos listos. Te explicamos cada permiso antes de pedirlo.',
        ),
        if (ready < list.length)
          button(
            ready == 0 ? 'Empezar guía (3 min)' : 'Continuar guía',
            () => openGuide(),
          ),
      ],
      leading: Icon(
        ready == list.length ? Icons.verified : Icons.settings_suggest_outlined,
        color: brandColor,
      ),
    );
  }

  Widget onboarding() => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      card('Un espacio para acompañarte', const [
        Icon(Icons.favorite_border, size: 54, color: brandColor),
        SizedBox(height: 14),
        Text(
          'Responde cuestionarios cortos sobre cómo te sientes y pide hablar con el equipo de psicología de tu colegio cuando lo necesites. Tú decides qué información opcional compartir.',
        ),
      ]),
      card('Ingresa con tu invitación', [
        const Text(
          'Tu colegio te entregó una invitación (un enlace o un texto largo) y, por separado, un código de 8 números.',
        ),
        const SizedBox(height: 14),
        TextField(
          controller: invitation,
          autocorrect: false,
          minLines: 1,
          maxLines: 3,
          decoration: const InputDecoration(
            labelText: 'Invitación personal',
            helperText: 'Puedes pegar el enlace completo.',
          ),
          onChanged: (v) {
            final parsed = parseInvitation(v, server.text);
            if (parsed.server != server.text && parsed.server.isNotEmpty) {
              setState(() => server.text = parsed.server);
            }
          },
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
        const SizedBox(height: 8),
        if (editServer)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: TextField(
              controller: server,
              keyboardType: TextInputType.url,
              decoration: const InputDecoration(
                labelText: 'Dirección HTTPS del colegio',
                helperText: 'Se completa sola si pegas el enlace de invitación.',
              ),
            ),
          )
        else
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton(
              onPressed: () => setState(() => editServer = true),
              child: const Text('Cambiar dirección del colegio'),
            ),
          ),
        button('Vincular mi teléfono', () {
          final parsed = parseInvitation(invitation.text, server.text);
          action('schoolEnroll', {
            'server': parsed.server,
            'invitation': parsed.token,
            'code': code.text.trim(),
          });
        }),
      ]),
    ],
  );

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
              destinations: [
                const NavigationDestination(
                  icon: Icon(Icons.home_outlined),
                  label: 'Inicio',
                ),
                NavigationDestination(
                  icon: Badge(
                    isLabelVisible: form != null,
                    child: const Icon(Icons.assignment_outlined),
                  ),
                  label: 'Cuestionario',
                ),
                const NavigationDestination(
                  icon: Icon(Icons.chat_bubble_outline),
                  label: 'Solicitudes',
                ),
                const NavigationDestination(
                  icon: Icon(Icons.shield_outlined),
                  label: 'Participación',
                ),
              ],
            )
          : null,
      body: SafeArea(
        child: ListView(
          controller: scroll,
          padding: const EdgeInsets.all(16),
          children: [
            if (busy) const LinearProgressIndicator(),
            if (message.isNotEmpty)
              Semantics(
                liveRegion: true,
                child: Container(
                  padding: const EdgeInsets.all(14),
                  margin: const EdgeInsets.only(bottom: 16),
                  decoration: BoxDecoration(
                    color: const Color(0xffe3f2f0),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(message),
                ),
              ),
            if (status['reauth_required'] == true)
              card('Tu acceso necesita renovarse', [
                const Text(
                  'Pide una nueva invitación al colegio. Para usarla se borrarán los borradores y envíos que queden en este teléfono.',
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
            if (!enrolled)
              onboarding()
            else if (tab == 0) ...[
              card('Hola, ${home['name'] ?? 'bienvenido'}', [
                Text(
                  auth['ready'] == true
                      ? 'Tu espacio de acompañamiento está disponible.'
                      : auth['minor'] == true && auth['guardian'] != true
                      ? 'Estamos esperando la autorización de tu madre, padre o apoderado. Cuando llegue, podrás continuar en Participación.'
                      : 'Antes de empezar, lee la información de participación y decide si quieres participar.',
                ),
                if (home['pilot_enabled'] == false)
                  const Padding(
                    padding: EdgeInsets.only(top: 8),
                    child: Text(
                      'El colegio aún no activó el piloto. Por ahora no se recogen datos.',
                    ),
                  ),
                if (auth['ready'] != true)
                  button(
                    'Revisar mi participación',
                    () => setState(() => tab = 3),
                  ),
                if (form != null && auth['ready'] == true)
                  button(
                    isPhq
                        ? 'Responder cuestionario (2 min)'
                        : 'Responder ${(form!['title'] ?? 'pregunta').toString().toLowerCase()}',
                    () {
                      setState(() => tab = 1);
                      refresh();
                    },
                  ),
              ]),
              if (auth['ready'] == true) setupCard(),
              card(
                '¿Quieres hablar con alguien?',
                [
                  const Text(
                    'Pide que el equipo de psicología de tu colegio te contacte. No necesitas explicar el motivo.',
                  ),
                  button(
                    'Quiero que me contacten',
                    requestSupport,
                    secondary: true,
                  ),
                ],
                leading: const Icon(Icons.chat_outlined, color: brandColor),
              ),
              coverage(),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 4),
                child: Text(
                  'Envíos pendientes: ${status['outbox_pending'] ?? 0} · Última sincronización: ${friendlyDate(status['last_sync'])}',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ),
            ] else if (tab == 1) ...[
              if (form == null)
                card(
                  !formsLoaded
                      ? (formsUnavailable
                            ? 'Sin conexión'
                            : 'Consultando cuestionario…')
                      : 'No tienes cuestionarios pendientes',
                  [
                    Text(
                      auth['ready'] != true
                          ? 'Primero completa tu participación.'
                          : (status['outbox_pending'] ?? 0) > 0
                          ? 'Tu respuesta puede estar esperando internet. Toca sincronizar (arriba a la derecha) para enviarla.'
                          : home['next_questionnaire'] != null
                          ? 'El próximo cuestionario aparecerá aquí desde el ${friendlyDate(home['next_questionnaire'], time: false)}. Te avisaremos.'
                          : 'Aparecerá aquí automáticamente.',
                    ),
                    button(
                      'Quiero que me contacten',
                      requestSupport,
                      secondary: true,
                    ),
                  ],
                )
              else
                questionnaire(),
              historyCard(),
            ] else if (tab == 2) ...[
              card('Mis solicitudes', [
                const Text(
                  'Cuando pides que te contacten, el equipo lo ve en su bandeja y coordina contigo.',
                ),
                button(
                  'Quiero que me contacten',
                  requestSupport,
                ),
                for (final r in requests['requests'] ?? [])
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: const Icon(Icons.mark_chat_read_outlined),
                    title: Text(
                      'Solicitud del ${friendlyDate(r['created_at'], time: false)}',
                    ),
                    subtitle: Text(requestStates[r['state']] ?? '${r['state']}'),
                  ),
              ]),
              card('Mis citas', [
                if ((requests['appointments'] ?? []).isEmpty)
                  const Text('Todavía no tienes citas programadas.'),
                for (final a in requests['appointments'] ?? [])
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Text(
                          friendlyDate(a['date']),
                          style: const TextStyle(fontWeight: FontWeight.w600),
                        ),
                        if ((a['place'] ?? '').toString().isNotEmpty)
                          Text('Lugar: ${a['place']}'),
                        Text(appointmentStates[a['state']] ?? '${a['state']}'),
                        if (a['state'] == 'pending')
                          button(
                            'Confirmar asistencia',
                            () => action('schoolConfirm', {'id': a['id']}),
                          ),
                      ],
                    ),
                  ),
              ]),
              if (deliveryLog.isNotEmpty)
                card('Estado de mis envíos', [
                  const Text(
                    'Lo que envías se guarda cifrado en el teléfono hasta que el equipo lo recibe. Nada se marca como recibido si no llegó.',
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
                            : 'Datos de sensores que vencieron sin enviarse. No afecta tus cuestionarios ni solicitudes.',
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
              coverage(),
            ] else ...[
              if (auth['ready'] == true) permissionCard(),
              if (auth['ready'] == true)
                Card(
                  margin: const EdgeInsets.only(bottom: 16),
                  child: ExpansionTile(
                    shape: const Border(),
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
        if (auth['ready'] != true && (home['purpose'] ?? '').toString().isNotEmpty)
          Text(
            home['purpose'],
            style: const TextStyle(fontWeight: FontWeight.w600),
          ),
        const SizedBox(height: 12),
        Text(
          home['document'] ??
              'Actualiza para leer la información de participación.',
        ),
        if (auth['minor'] == true && auth['guardian'] != true)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 16),
            child: Text(
              'Falta la autorización de tu madre, padre o apoderado. Se actualizará sola cuando la envíen.',
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
          const Text(
            'Elige qué compartir. Puedes cambiarlo cuando quieras; para activar un permiso usa la guía de permisos.',
          ),
          toggle(
            'Uso de pantalla',
            usage,
            (v) => setState(() => usage = v),
            subtitle:
                'Cuándo y cuánto se enciende la pantalla. No vemos apps, mensajes, llamadas ni contenido.',
          ),
          toggle(
            'Ubicación',
            location,
            (v) => setState(() {
              location = v;
              if (!v) raw = false;
            }),
            subtitle:
                'Resúmenes calculados en tu teléfono: distancia, tiempo en casa y asistencia al colegio.',
          ),
          toggle(
            'Pasos',
            steps,
            (v) => setState(() => steps = v),
            subtitle:
                'Necesita un sensor compatible; no mide toda tu actividad física.',
          ),
          if (location) ...[
            toggle(
              'Enviar coordenadas al servidor',
              raw,
              (v) => setState(() => raw = v),
              subtitle:
                  'Opcional y poco común. Si lo dejas apagado, las coordenadas nunca salen de tu teléfono.',
            ),
            const Padding(
              padding: EdgeInsets.only(top: 8),
              child: Text(
                '¿Estás en tu casa ahora? Puedes marcarla para calcular el tiempo que pasas en casa. Se guarda solo en tu teléfono.',
              ),
            ),
            button(
              'Marcar este lugar como mi casa',
              () => action('schoolHomeZone', {'clear': false}),
              secondary: true,
            ),
            if (home['has_home_zone'] == true || status['home_zone'] == true)
              button(
                'Borrar mi casa',
                () => action('schoolHomeZone', {'clear': true}),
                secondary: true,
              ),
          ],
          toggle(
            'Permitir uso en investigación',
            research,
            (v) => setState(() => research = v),
            subtitle:
                'Tus datos, sin tu nombre, pueden usarse para mejorar la app.',
          ),
          toggle(
            'Recibir recordatorios',
            reminders,
            (v) => setState(() => reminders = v),
          ),
          if (reminders)
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                icon: const Icon(Icons.schedule),
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
                label: Text('Hora del recordatorio: ${reminder.format(context)}'),
              ),
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
      if (auth['student'] == true) card('Retirar mi participación', [
        const Text(
          'Se detiene la captura y se pide borrar tus datos. Si no hay internet, la captura se detiene igual y el retiro se envía después.',
        ),
        button('Retirarme', () async {
          final yes = await showDialog<bool>(
            context: context,
            builder: (c) => AlertDialog(
              title: const Text('¿Retirar tu participación?'),
              content: const Text(
                'Se pedirá borrar tus datos del sistema. Para volver necesitarás una invitación nueva.',
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
