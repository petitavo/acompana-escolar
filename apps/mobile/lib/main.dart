import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'school.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  String mode = '';
  try {
    final result = await const MethodChannel(
      'pe.upc.acompana/collector',
    ).invokeMethod<String>('status');
    mode = jsonDecode(result ?? '{}')['mode'] ?? '';
  } catch (_) {}
  runApp(
    mode == 'LAB' || mode == 'DEMO' ? const LaboratoryApp() : const SchoolApp(),
  );
}

class LaboratoryApp extends StatelessWidget {
  const LaboratoryApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Acompaña · Laboratorio',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF1D4ED8)),
      scaffoldBackgroundColor: const Color(0xFFF8FAFC),
      inputDecorationTheme: const InputDecorationTheme(
        border: OutlineInputBorder(),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(52)),
      ),
    ),
    home: const LaboratoryHome(),
  );
}

class LaboratoryHome extends StatefulWidget {
  const LaboratoryHome({super.key});
  @override
  State<LaboratoryHome> createState() => _LaboratoryHomeState();
}

class _LaboratoryHomeState extends State<LaboratoryHome>
    with WidgetsBindingObserver {
  static const bridge = MethodChannel('pe.upc.acompana/collector');
  Map<String, dynamic> state = {};
  Map<String, dynamic>? form;
  Map<String, int> answers = {};
  List<dynamic> history = [];
  final server = TextEditingController(
    text: const String.fromEnvironment('API_URL'),
  );
  final invitation = TextEditingController();
  String message = '';
  bool busy = false, adult = false, share = false;
  int page = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    refresh();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    server.dispose();
    invitation.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState value) {
    if (value == AppLifecycleState.resumed) refresh();
  }

  Future<dynamic> call(String method, [Map<String, dynamic>? args]) async {
    final raw = await bridge.invokeMethod<String>(method, args);
    return raw == null ? null : jsonDecode(raw);
  }

  Future<void> refresh() async {
    try {
      final value = await call('status');
      if (mounted) setState(() => state = Map<String, dynamic>.from(value));
      if (state['enrolled'] == true) {
        try {
          final forms = await call('forms') as List;
          final draft = Map<String, dynamic>.from(await call('draft'));
          if (mounted) {
            setState(() {
              form = forms.isEmpty
                  ? null
                  : Map<String, dynamic>.from(forms.first);
              answers = draft.map((k, v) => MapEntry(k, v as int));
            });
          }
        } catch (_) {
          if (mounted) {
            setState(
              () => message =
                  'Sin conexión. La captura y la cola local siguen disponibles.',
            );
          }
        }
      }
    } on PlatformException catch (e) {
      if (mounted) {
        setState(
          () => message = e.message ?? 'No se pudo consultar el colector',
        );
      }
    }
  }

  Future<bool> act(String method, [Map<String, dynamic>? args]) async {
    if (busy) return false;
    setState(() {
      busy = true;
      message = '';
    });
    try {
      final value = await call(method, args);
      if (value is Map && mounted) {
        setState(() => state = Map<String, dynamic>.from(value));
      }
      if (mounted) {
        setState(
          () => message = (state['rejected'] ?? 0) > 0
              ? 'Hay registros rechazados. Revisa Mis datos y consulta al investigador.'
              : state['outbox_pending'] == 0
              ? 'Operación completada. Sin envíos pendientes.'
              : 'Datos guardados localmente; ${state['outbox_pending']} registros pendientes de envío.',
        );
      }
      return true;
    } on PlatformException catch (e) {
      if (mounted) {
        setState(
          () => message =
              e.message ?? 'Sin conexión. Los datos pendientes se conservan.',
        );
      }
      return false;
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Widget card(String title, List<Widget> children) => Card(
    margin: const EdgeInsets.only(bottom: 18),
    color: Colors.white,
    child: Padding(
      padding: const EdgeInsets.all(22),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 16),
          ...children,
        ],
      ),
    ),
  );
  Widget line(String name, dynamic value) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 8),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(child: Text(name)),
        const SizedBox(width: 15),
        Flexible(
          child: Text(
            value == null || value == '' ? 'Todavía no disponible' : '$value',
            textAlign: TextAlign.end,
            style: const TextStyle(fontWeight: FontWeight.w600),
          ),
        ),
      ],
    ),
  );
  Widget button(String text, VoidCallback onTap, {bool secondary = false}) =>
      Padding(
        padding: const EdgeInsets.symmetric(vertical: 5),
        child: secondary
            ? OutlinedButton(
                onPressed: busy ? null : onTap,
                style: OutlinedButton.styleFrom(
                  minimumSize: const Size.fromHeight(52),
                ),
                child: Text(text),
              )
            : FilledButton(onPressed: busy ? null : onTap, child: Text(text)),
      );

  @override
  Widget build(BuildContext context) {
    final enrolled = state['enrolled'] == true;
    final active = state['active'] == true;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Acompaña Escolar'),
        actions: [
          IconButton(
            onPressed: refresh,
            tooltip: 'Actualizar estado',
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      bottomNavigationBar: enrolled
          ? NavigationBar(
              selectedIndex: page,
              onDestinationSelected: (p) => setState(() => page = p),
              destinations: const [
                NavigationDestination(
                  icon: Icon(Icons.home_outlined),
                  label: 'Inicio',
                ),
                NavigationDestination(
                  icon: Icon(Icons.data_usage),
                  label: 'Mis datos',
                ),
                NavigationDestination(
                  icon: Icon(Icons.assignment_outlined),
                  label: 'Cuestionarios',
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
          padding: const EdgeInsets.all(20),
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              margin: const EdgeInsets.only(bottom: 20),
              decoration: BoxDecoration(
                color: state['mode'] == 'DEMO'
                    ? const Color(0xFFFFF4D6)
                    : const Color(0xFFE8F5EF),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                state['mode'] == 'DEMO'
                    ? 'Demostración · datos ficticios'
                    : 'LAB · prueba interna con adultos',
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
            ),
            if (!enrolled) ...[
              card('Bienvenido al laboratorio', const [
                Text(
                  'Participa en una prueba de ingeniería con tu propio teléfono. No se diagnostica ni se utiliza esta app para atender emergencias.',
                ),
                SizedBox(height: 12),
                Text(
                  'Se pueden registrar eventos de pantalla, bloqueo y actividad del dispositivo. No se recoge contenido de mensajes, llamadas, contactos, micrófono, cámara ni ubicación.',
                ),
              ]),
              card('Vincular mi teléfono', [
                TextField(
                  controller: server,
                  decoration: const InputDecoration(
                    labelText: 'URL HTTPS del laboratorio',
                    hintText: 'https://laboratorio.local:8443',
                  ),
                  keyboardType: TextInputType.url,
                ),
                const SizedBox(height: 18),
                TextField(
                  controller: invitation,
                  decoration: const InputDecoration(
                    labelText: 'Invitación de un solo uso',
                  ),
                  autocorrect: false,
                ),
                const SizedBox(height: 16),
                button('Vincular teléfono', () async {
                  await act('enroll', {
                    'server': server.text.trim(),
                    'invitation': invitation.text.trim(),
                  });
                  await refresh();
                }),
              ]),
            ] else if (!active && state['local_status'] == 'pending') ...[
              card('Tú decides qué compartir', [
                const Text(
                  'Puedes pausar o retirarte. Se conserva solo información técnica autorizada: eventos locales por 7 días y datos de prueba del servidor según la política del laboratorio.',
                ),
                CheckboxListTile(
                  contentPadding: EdgeInsets.zero,
                  value: adult,
                  onChanged: (v) => setState(() => adult = v ?? false),
                  title: const Text(
                    'Soy adulto y acepto esta prueba interna. Comprendo los datos que se registran.',
                  ),
                ),
                CheckboxListTile(
                  contentPadding: EdgeInsets.zero,
                  value: share,
                  onChanged: (v) => setState(() => share = v ?? false),
                  title: const Text(
                    'Compartir detalle de aplicaciones para la prueba (opcional)',
                  ),
                ),
                FilledButton(
                  onPressed: adult && !busy
                      ? () async {
                          await act('participation', {
                            'action': 'consent',
                            'share': share,
                          });
                          await refresh();
                        }
                      : null,
                  child: const Text('Aceptar y comenzar'),
                ),
              ]),
            ] else if (page == 0) ...[
              card('Hola, ${state['pseudonym']}', [
                line('Participación', active ? 'Activa' : 'Pausada / retirada'),
                line('Última sincronización', state['last_sync']),
                line('Envíos pendientes', state['outbox_pending']),
                if (state['mode'] == 'DEMO')
                  const Text(
                    'En DEMO solo se prueban formularios. Los datos de uso reales se envían exclusivamente a un servidor LAB.',
                  ),
                button('Sincronizar ahora', () => act('sync')),
                button(
                  'Ir al cuestionario',
                  () => setState(() => page = 2),
                  secondary: true,
                ),
              ]),
              card('Acceso de uso del dispositivo', [
                line(
                  'Estado comprobado',
                  state['usage_access'] == 'available'
                      ? 'Permiso disponible'
                      : 'Falta permiso',
                ),
                const Text(
                  'Puedes usar los formularios sin dar este permiso. Android decide cuándo permite consultar eventos; conceder acceso no demuestra que ya se capturaron.',
                ),
                button('Abrir ajustes de acceso de uso', () async {
                  await bridge.invokeMethod('openUsageSettings');
                }, secondary: true),
                if (state['mode'] == 'LAB')
                  button('Capturar ahora', () => act('capture')),
                const Text(
                  'La captura periódica puede demorarse por ahorro de batería. Forzar el cierre impide el trabajo hasta volver a abrir la app.',
                  style: TextStyle(fontSize: 13),
                ),
              ]),
              card('Solicitud de contacto', [
                const Text(
                  'Se prueba el flujo; no existe atención de emergencia garantizada. Solo se confirma el envío después de recibir respuesta del servidor.',
                ),
                button(
                  'Quiero que me contacten',
                  () => act('contact'),
                  secondary: true,
                ),
              ]),
            ] else if (page == 1) ...[
              card('Mis datos técnicos', [
                line('Seudónimo', state['pseudonym']),
                line('Eventos locales permitidos', state['events_local']),
                line('Pendientes de envío', state['outbox_pending']),
                line('Rechazos que requieren revisión', state['rejected']),
                line('Última consulta', state['last_query']),
                line('Acceso de uso', state['usage_access']),
                line(
                  'Detalle de apps',
                  state['share_packages'] == true
                      ? 'Autorizado'
                      : 'No compartido',
                ),
                const Divider(),
                line('GPS / movilidad', 'No implementado'),
                line('Pasos', 'No implementado'),
                line('Estimación de sueño', 'No implementado'),
                const Text(
                  'El estado interactivo de la pantalla no mide atención humana. Uso nocturno del teléfono no equivale a horas dormidas.',
                ),
              ]),
            ] else if (page == 2) ...[
              card('Cuestionario de prueba', [
                if (form == null)
                  const Text(
                    'Todavía no se descargó el formulario. Conecta el teléfono y actualiza.',
                  ),
                if (form != null) ...[
                  Text(form!['notice'] as String),
                  const SizedBox(height: 20),
                  for (final q in form!['questions'] as List) ...[
                    Text(
                      q['text'],
                      style: const TextStyle(fontWeight: FontWeight.w600),
                    ),
                    RadioGroup<int>(
                      groupValue: answers[q['id']],
                      onChanged: (v) async {
                        if (!active) return;
                        setState(() => answers[q['id']] = v!);
                        await call('draft', {'value': jsonEncode(answers)});
                      },
                      child: Column(
                        children: [
                          for (final option in form!['options'] as List)
                            RadioListTile<int>(
                              contentPadding: EdgeInsets.zero,
                              title: Text(option['label']),
                              value: option['value'],
                              enabled: active,
                            ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 14),
                  ],
                  FilledButton(
                    onPressed:
                        active &&
                            !busy &&
                            answers.length ==
                                (form!['questions'] as List).length
                        ? () async {
                            final at = DateTime.now();
                            final body = {
                              'instrument_code': form!['instrument_id'],
                              'answers': answers,
                              'applied_at': at.toUtc().toIso8601String(),
                              'recall_start': DateTime(
                                at.year,
                                at.month,
                                at.day,
                              ).toUtc().toIso8601String(),
                              'recall_end': at.toUtc().toIso8601String(),
                            };
                            final saved = await act('submit', {
                              'body': jsonEncode(body),
                            });
                            if (saved && mounted) setState(() => answers = {});
                          }
                        : null,
                    child: const Text('Guardar y enviar cuestionario'),
                  ),
                ],
                button('Consultar historial', () async {
                  try {
                    final rows = await call('history') as List;
                    setState(() => history = rows);
                  } catch (_) {
                    setState(
                      () => message = 'Sin conexión para consultar historial.',
                    );
                  }
                }, secondary: true),
                for (final r in history.take(10))
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: const Icon(Icons.check_circle_outline),
                    title: Text(r['detail']['instrument_code']),
                    subtitle: Text(r['detail']['applied_at']),
                    trailing: const Text('Enviado'),
                  ),
              ]),
            ] else ...[
              card('Control de participación', [
                line('Estado local', state['local_status']),
                const Text(
                  'Pausar detiene la captura y cancela los registros de uso aún no enviados. Reanudar comienza un nuevo período; no recupera el período pausado.',
                ),
                if (state['local_status'] != 'revoked')
                  button(
                    active ? 'Pausar participación' : 'Reanudar participación',
                    () => act('participation', {
                      'action': active ? 'pause' : 'resume',
                      'share': state['share_packages'] == true,
                    }),
                    secondary: true,
                  ),
                if (state['local_status'] != 'revoked')
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    value: state['share_packages'] == true,
                    onChanged: busy
                        ? null
                        : (v) => act('participation', {
                            'action': 'package_policy',
                            'share': v,
                          }),
                    title: const Text(
                      'Compartir detalle de aplicaciones para la prueba',
                    ),
                  ),
                button(
                  'Sincronizar cambios pendientes',
                  () => act('sync'),
                  secondary: true,
                ),
                if (state['local_status'] != 'revoked')
                  button('Retirarme y solicitar borrado', () async {
                    final confirm = await showDialog<bool>(
                      context: context,
                      builder: (context) => AlertDialog(
                        title: const Text('¿Retirarte de la prueba?'),
                        content: const Text(
                          'Se detendrá la captura. El servidor eliminará tus datos de prueba al procesar la solicitud. Si no hay conexión, la solicitud quedará pendiente.',
                        ),
                        actions: [
                          TextButton(
                            onPressed: () => Navigator.pop(context, false),
                            child: const Text('Cancelar'),
                          ),
                          FilledButton(
                            onPressed: () => Navigator.pop(context, true),
                            child: const Text('Retirarme'),
                          ),
                        ],
                      ),
                    );
                    if (confirm == true) await act('delete');
                  }, secondary: true),
              ]),
            ],
            if (busy) const LinearProgressIndicator(),
            if (message.isNotEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 14),
                child: Semantics(
                  liveRegion: true,
                  child: Text(
                    message,
                    style: const TextStyle(color: Color(0xFF0F766E)),
                  ),
                ),
              ),
            const SizedBox(height: 20),
            const Text(
              'Laboratorio de ingeniería · UPC\nSin diagnóstico ni puntuación predictiva para participantes.',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 13, color: Color(0xFF64748B)),
            ),
          ],
        ),
      ),
    );
  }
}
