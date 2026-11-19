import 'dart:async';
import 'package:flutter/material.dart';

/// Pasos de "Activa los permisos". Cada uno es un permiso o ajuste de Android.
class SetupStep {
  const SetupStep({
    required this.kind,
    required this.title,
    required this.icon,
    this.hint = '',
    this.preference,
  });
  final String kind;
  final String title;
  final IconData icon;

  /// Una línea, solo para los pasos que abren Ajustes (qué tocar allí).
  final String hint;

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
    // Sin ventana de Android: se mide con el encendido/apagado de la pantalla.
    const SetupStep(
      kind: 'usage',
      preference: 'usage',
      title: 'Uso de pantalla',
      icon: Icons.phone_android,
    ),
    const SetupStep(
      kind: 'notifications',
      preference: 'reminders',
      title: 'Avisos',
      icon: Icons.notifications_active_outlined,
    ),
    const SetupStep(
      kind: 'location',
      preference: 'location',
      title: 'Ubicación',
      icon: Icons.location_on_outlined,
    ),
  ];
  if (status['steps_supported'] != false) {
    steps.add(
      const SetupStep(
        kind: 'steps',
        preference: 'steps',
        title: 'Pasos',
        icon: Icons.directions_walk,
      ),
    );
  }
  steps.add(
    const SetupStep(
      kind: 'battery',
      title: 'Batería',
      icon: Icons.battery_charging_full,
    ),
  );
  if (['precise', 'approximate'].contains(status['location_permission'])) {
    steps.add(
      SetupStep(
        kind: 'background',
        preference: 'location',
        title: 'Ubicación siempre',
        icon: Icons.my_location,
        hint:
            'Se abrirá Ajustes: elige ${brand == 'xiaomi' ? '"Permitir siempre"' : '"Permitir todo el tiempo"'} y vuelve.',
      ),
    );
  }
  if (autostartBrands.contains(brand) || device['autostart_screen'] == true) {
    steps.add(
      const SetupStep(
        kind: 'autostart',
        title: 'Inicio automático',
        icon: Icons.restart_alt,
        hint: 'Se abrirá Ajustes: activa "Acompaña Escolar" y vuelve.',
      ),
    );
  }
  return steps;
}

/// Estado de un paso a partir del estado nativo y de la política guardada.
String stepState(SetupStep s, Map status, Map device, Map policy) {
  final granted = switch (s.kind) {
    'usage' => true,
    'notifications' => status['notifications_permission'] == true,
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
  'ready' => const Color(0xff15803d),
  'approximate' => const Color(0xffb45309),
  'pending' => const Color(0xffe0603e),
  _ => const Color(0xff64748b),
};

/// Pasos que salen de la app a Ajustes: antes se avisa qué tocar allí.
bool leavesApp(SetupStep s) => s.kind == 'background' || s.kind == 'autostart';

class PermissionGuide extends StatefulWidget {
  const PermissionGuide({
    super.key,
    required this.loadStatus,
    required this.loadDevice,
    required this.policy,
    required this.request,
    required this.confirm,
    required this.enableAll,
    this.initialKind,
  });

  /// Guarda de una vez todas las preferencias (compartir pantalla, ubicación, pasos,
  /// avisos). Devuelve 'confirmed', 'offline', 'rejected' o null si no se pudo.
  final Future<String?> Function() enableAll;

  final Future<Map<String, dynamic>> Function() loadStatus;
  final Future<Map<String, dynamic>> Function() loadDevice;
  final Map Function() policy;

  /// Pide el permiso (guardando antes la preferencia si hace falta). Devuelve el resultado.
  final Future<String?> Function(String kind) request;

  /// Marca un ajuste que Android no permite comprobar (inicio automático).
  final Future<void> Function(String key) confirm;

  /// Si viene, se pide solo ese permiso al abrir.
  final String? initialKind;

  @override
  State<PermissionGuide> createState() => _PermissionGuideState();
}

/// Una sola pantalla: lista corta de permisos y un botón que los pide todos seguidos.
class _PermissionGuideState extends State<PermissionGuide>
    with WidgetsBindingObserver {
  Map<String, dynamic> status = {}, device = {};
  bool busy = false, loaded = false, waitingReturn = false;
  String note = '';

  /// Pasos que el alumno rechazó en esta visita: no se vuelven a pedir solos.
  final skipped = <String>{};
  final blocked = <String>{};

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    reload().then((_) {
      final kind = widget.initialKind;
      if (kind != null && mounted) {
        final s = steps.where((x) => x.kind == kind);
        if (s.isNotEmpty && stateOf(s.first) != 'ready') runOne(s.first);
      }
    });
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState s) {
    // Al volver de Ajustes o de una ventana de Android: revisar y seguir con lo que falta.
    if (s != AppLifecycleState.resumed) return;
    if (waitingReturn) {
      waitingReturn = false;
      reload().then((_) => runAll());
    } else {
      reload();
    }
  }

  List<SetupStep> get steps => setupSteps(status, device);
  String stateOf(SetupStep s) => stepState(s, status, device, widget.policy());

  /// Lo que falta y el alumno eligió compartir (lo "No compartido" no se pide).
  List<SetupStep> get missing => steps
      .where((s) => ['off', 'pending', 'approximate'].contains(stateOf(s)))
      .toList();

  SetupStep? get next {
    for (final s in missing) {
      if (s.kind == 'usage') continue;
      if (!skipped.contains(s.kind) && !blocked.contains(s.kind)) return s;
    }
    return null;
  }

  /// Una sola vez y antes de cualquier ventana: así Android responde al instante.
  Future<bool> saveChoices() async {
    if (!missing.any((s) => stateOf(s) == 'off')) return true;
    final state = await widget.enableAll();
    if (!mounted) return false;
    if (state != 'confirmed') {
      setState(
        () => note = state == 'rejected'
            ? 'No se pudo guardar tu elección. Revisa la pestaña Participación.'
            : 'No hay conexión con el colegio. Revisa tu internet y vuelve a tocar el botón.',
      );
      return false;
    }
    await reload();
    return mounted;
  }

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
      });
    } catch (_) {
      if (mounted) setState(() => loaded = true);
    }
  }

  /// Pide un paso. Devuelve false si hay que detener la cadena.
  Future<bool> ask(SetupStep s, {bool settings = false}) async {
    final result = await widget.request(settings ? 'settings' : s.kind);
    if (!mounted) return false;
    if (result == 'offline' || result == 'rejected') {
      setState(
        () => note = result == 'offline'
            ? 'No hay conexión con el colegio. Revisa tu internet y vuelve a tocar el botón.'
            : 'No se pudo guardar tu elección. Revisa la pestaña Participación.',
      );
      return false;
    }
    if (result == 'settings_opened') {
      if (s.kind == 'autostart') await widget.confirm('autostart');
      waitingReturn = true;
      return false;
    }
    await reload();
    if (!mounted) return false;
    if (result == 'blocked') blocked.add(s.kind);
    if (stateOf(s) != 'ready') skipped.add(s.kind);
    return true;
  }

  /// Pide seguidos todos los permisos que faltan. Se detiene antes de los que
  /// abren Ajustes (el botón muestra qué hacer allí) y continúa al volver.
  Future<void> runAll({bool confirmed = false}) async {
    if (busy) return;
    setState(() {
      busy = true;
      note = '';
    });
    try {
      if (!await saveChoices()) return;
      while (mounted) {
        final s = next;
        if (s == null) break;
        if (leavesApp(s) && !confirmed) break;
        confirmed = false;
        if (!await ask(s)) break;
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> runOne(SetupStep s) async {
    if (busy) return;
    setState(() {
      busy = true;
      note = '';
      skipped.remove(s.kind);
    });
    try {
      if (!await saveChoices()) return;
      if (s.kind != 'usage') await ask(s, settings: blocked.contains(s.kind));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final list = steps;
    final ready = list.where((s) => stateOf(s) == 'ready').length;
    final n = next;
    final anyOff = list.any((s) => stateOf(s) == 'off');
    final done = n == null && !anyOff;
    final label = busy
        ? 'Un momento…'
        : done
        ? (missing.isEmpty ? 'Listo' : 'Volver')
        : n != null && leavesApp(n)
        ? 'Abrir Ajustes'
        : ready == 0
        ? 'Activar permisos'
        : 'Continuar';
    return Scaffold(
      appBar: AppBar(title: const Text('Permisos')),
      body: !loaded
          ? const Center(child: CircularProgressIndicator())
          : SafeArea(
              child: Column(
                children: [
                  Expanded(
                    child: ListView(
                      padding: const EdgeInsets.fromLTRB(22, 8, 22, 8),
                      children: [
                        Center(
                          child: TweenAnimationBuilder<double>(
                            tween: Tween(
                              begin: 0,
                              end: list.isEmpty ? 0 : ready / list.length,
                            ),
                            duration: const Duration(milliseconds: 600),
                            curve: Curves.easeOutCubic,
                            builder: (context, v, _) => SizedBox(
                              width: 112,
                              height: 112,
                              child: Stack(
                                fit: StackFit.expand,
                                children: [
                                  CircularProgressIndicator(
                                    value: v,
                                    strokeWidth: 10,
                                    strokeCap: StrokeCap.round,
                                    backgroundColor: theme.colorScheme.primary
                                        .withValues(alpha: 0.12),
                                  ),
                                  Center(
                                    child: AnimatedSwitcher(
                                      duration: const Duration(
                                        milliseconds: 300,
                                      ),
                                      transitionBuilder: (c, a) =>
                                          ScaleTransition(scale: a, child: c),
                                      child: missing.isEmpty
                                          ? Icon(
                                              Icons.check_rounded,
                                              key: const ValueKey('ok'),
                                              size: 52,
                                              color: theme.colorScheme.primary,
                                            )
                                          : Text(
                                              '$ready/${list.length}',
                                              key: ValueKey(ready),
                                              style: theme
                                                  .textTheme
                                                  .headlineSmall
                                                  ?.copyWith(
                                                    fontWeight: FontWeight.w800,
                                                  ),
                                            ),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(height: 18),
                        Text(
                          missing.isEmpty
                              ? '¡Tu teléfono está listo!'
                              : 'Activa los permisos',
                          textAlign: TextAlign.center,
                          style: theme.textTheme.headlineSmall?.copyWith(
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          missing.isEmpty
                              ? 'Todo activo. Puedes cambiarlo cuando quieras en Participación.'
                              : 'Android te mostrará unas ventanas. Toca "Permitir" en cada una.',
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'Nunca vemos mensajes, fotos ni lo que escribes.',
                          textAlign: TextAlign.center,
                          style: TextStyle(color: Colors.grey.shade600),
                        ),
                        const SizedBox(height: 16),
                        for (var i = 0; i < list.length; i++)
                          FadeSlide(index: i, child: row(list[i])),
                      ],
                    ),
                  ),
                  Padding(
                    padding: const EdgeInsets.fromLTRB(22, 4, 22, 16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        if (note.isNotEmpty)
                          Padding(
                            padding: const EdgeInsets.only(bottom: 10),
                            child: Text(
                              note,
                              style: const TextStyle(color: Color(0xffb45309)),
                            ),
                          )
                        else if (!busy && n != null && leavesApp(n))
                          Padding(
                            padding: const EdgeInsets.only(bottom: 10),
                            child: Text(n.hint, textAlign: TextAlign.center),
                          ),
                        FilledButton(
                          key: const ValueKey('guide-main'),
                          onPressed: busy
                              ? null
                              : done
                              ? () => Navigator.of(context).pop()
                              : () => runAll(
                                  confirmed: n != null && leavesApp(n),
                                ),
                          child: Text(label),
                        ),
                        if (!done)
                          TextButton(
                            onPressed: busy
                                ? null
                                : () => Navigator.of(context).pop(),
                            child: const Text('Ahora no'),
                          ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
    );
  }

  Widget row(SetupStep s) {
    final state = stateOf(s);
    final ready = state == 'ready';
    final color = stateColor(context, state);
    final isBlocked = blocked.contains(s.kind);
    final subtitle = ready
        ? 'Activo'
        : state == 'off'
        ? 'Se activará'
        : isBlocked
        ? 'Bloqueado: toca para abrir Ajustes'
        : skipped.contains(s.kind)
        ? 'No activado: toca para intentar'
        : state == 'approximate'
        ? 'Falta ubicación precisa'
        : 'Falta activar';
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        key: ValueKey('guide-row-${s.kind}'),
        leading: AnimatedContainer(
          duration: const Duration(milliseconds: 300),
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: ready ? color : color.withValues(alpha: 0.14),
          ),
          child: AnimatedSwitcher(
            duration: const Duration(milliseconds: 300),
            transitionBuilder: (c, a) => ScaleTransition(scale: a, child: c),
            child: Icon(
              ready ? Icons.check_rounded : s.icon,
              key: ValueKey(ready),
              color: ready ? Colors.white : color,
            ),
          ),
        ),
        title: Text(
          s.title,
          style: const TextStyle(fontWeight: FontWeight.w600),
        ),
        subtitle: Text(subtitle, style: TextStyle(color: color)),
        onTap: ready || busy ? null : () => runOne(s),
      ),
    );
  }
}

/// Entrada suave (aparece y sube un poco), escalonada por [index].
class FadeSlide extends StatelessWidget {
  const FadeSlide({super.key, required this.index, required this.child});
  final int index;
  final Widget child;
  @override
  Widget build(BuildContext context) => TweenAnimationBuilder<double>(
    tween: Tween(begin: 0, end: 1),
    duration: Duration(milliseconds: 380 + index * 90),
    curve: Interval(
      (index * 90) / (380 + index * 90),
      1,
      curve: Curves.easeOutCubic,
    ),
    builder: (context, v, child) => Opacity(
      opacity: v,
      child: Transform.translate(offset: Offset(0, 18 * (1 - v)), child: child),
    ),
    child: child,
  );
}
