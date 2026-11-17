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
          'Se abrirá una lista de Ajustes. Busca "Acompaña Escolar", tócala y activa el interruptor. Luego vuelve con la flecha de atrás. Android muestra un aviso general que dice que la app "podría ver qué apps usas": es el texto estándar de este permiso; nosotros no guardamos nombres de apps.${{'xiaomi': ' En Xiaomi la lista se llama "Acceso a datos de uso".', 'samsung': ' En Samsung la lista se llama "Acceso a datos de uso".', 'huawei': ' En Huawei la lista se llama "Acceso al uso de apps".', 'honor': ' En Honor la lista se llama "Acceso al uso de apps".'}[brand] ?? ''}',
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

/// Android 13+ bloquea "Acceso al uso" en apps instaladas fuera de Play Store.
const restrictedHelp = [
  'Cierra ese aviso.',
  'Toca "Abrir info de la app" (abajo).',
  'Toca ⋮ (arriba a la derecha) y luego "Permitir configuración restringida".',
  'Vuelve aquí y toca "Permitir" otra vez.',
];

/// Colores de cada paso: dan identidad a la guía sin depender del texto.
const stepColors = {
  'notifications': Color(0xffff7a59),
  'usage': Color(0xff7c6cf2),
  'location': Color(0xff0e9f8f),
  'background': Color(0xff0b7a8f),
  'steps': Color(0xfff59e0b),
  'battery': Color(0xff22a35a),
  'autostart': Color(0xffe2557a),
};

Color colorOf(String kind) => stepColors[kind] ?? const Color(0xff0e7c7b);

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
    'No hay conexión con el colegio en este momento. Revisa tu internet y vuelve a tocar el botón.',
  'rejected' =>
    'No se pudo guardar tu elección. Abre la pestaña Participación y revisa tu autorización.',
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
    final current = page > 0 && page <= list.length ? list[page - 1] : null;
    final accent = current == null
        ? Theme.of(context).colorScheme.primary
        : colorOf(current.kind);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Prepara tu teléfono'),
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(6),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 22),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: (page + 1) / total,
                minHeight: 6,
                color: accent,
                backgroundColor: accent.withValues(alpha: 0.15),
              ),
            ),
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
            padding: const EdgeInsets.fromLTRB(22, 18, 22, 8),
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

  /// Ilustración simple: el icono del paso dentro de círculos de su color.
  Widget badge(IconData icon, Color color, {double size = 112}) => Center(
    child: Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: color.withValues(alpha: 0.12),
      ),
      child: Center(
        child: Container(
          width: size * 0.66,
          height: size * 0.66,
          decoration: BoxDecoration(shape: BoxShape.circle, color: color),
          child: Icon(icon, color: Colors.white, size: size * 0.34),
        ),
      ),
    ),
  );

  Widget intro(int count) => frame(
    [
      badge(Icons.phone_android, Theme.of(context).colorScheme.primary),
      const SizedBox(height: 18),
      Text(
        'Vamos a preparar tu teléfono',
        style: Theme.of(
          context,
        ).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700),
        textAlign: TextAlign.center,
      ),
      const SizedBox(height: 10),
      Text('$count pasos cortos, unos 3 minutos.', textAlign: TextAlign.center),
      const SizedBox(height: 20),
      const _Tile(
        color: Color(0xff0e9f8f),
        icon: Icons.touch_app_outlined,
        text:
            'Antes de cada ventana de Android te decimos qué va a aparecer y qué tocar.',
      ),
      const _Tile(
        color: Color(0xff7c6cf2),
        icon: Icons.lock_outline,
        text:
            'Nunca vemos mensajes, fotos, llamadas, lo que escribes ni qué apps usas.',
      ),
      const _Tile(
        color: Color(0xffff7a59),
        icon: Icons.toggle_on_outlined,
        text: 'Todo es opcional. Puedes saltar un paso con "Ahora no".',
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
    final color = colorOf(s.kind);
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
    final failed = result != null && result != 'granted' && !ready;
    return frame(
      [
        Text(
          'Paso ${index + 1} de $count',
          textAlign: TextAlign.center,
          style: theme.textTheme.labelLarge?.copyWith(
            color: color,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 12),
        badge(
          ready ? Icons.check : s.icon,
          ready ? stateColor(context, 'ready') : color,
        ),
        const SizedBox(height: 14),
        Text(
          s.title,
          textAlign: TextAlign.center,
          style: theme.textTheme.headlineSmall?.copyWith(
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 8),
        Center(
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
            decoration: BoxDecoration(
              color: stateColor(context, state).withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Text(
              stateLabels[state] ?? state,
              style: TextStyle(
                color: stateColor(context, state),
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ),
        const SizedBox(height: 16),
        if (ready || result == 'granted')
          _Notice(
            color: stateColor(context, 'ready'),
            icon: Icons.check_circle,
            text: resultMessage('granted', s),
          )
        else ...[
          if (failed)
            _Notice(
              color: const Color(0xffd97706),
              icon: Icons.info_outline,
              text: resultMessage(result, s),
            ),
          _Box(
            color: color,
            icon: Icons.touch_app_outlined,
            title: 'Qué va a pasar',
            items: [s.how],
          ),
        ],
        _Box(
          color: const Color(0xff0e7c7b),
          icon: Icons.check,
          title: 'Para qué sirve',
          items: s.why,
        ),
        _Box(
          color: const Color(0xff64748b),
          icon: Icons.visibility_off_outlined,
          title: 'Lo que NO vemos',
          items: s.notSeen,
        ),
        if (s.kind == 'usage' && !ready)
          Card(
            margin: const EdgeInsets.only(top: 6),
            child: ExpansionTile(
              shape: const Border(),
              leading: const Icon(Icons.help_outline),
              title: const Text('¿Te salió "Configuración restringida"?'),
              childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
              children: [
                for (var i = 0; i < restrictedHelp.length; i++)
                  _Bullet(
                    icon: Icons.circle,
                    text: '${i + 1}. ${restrictedHelp[i]}',
                    color: color,
                  ),
                const SizedBox(height: 6),
                OutlinedButton(
                  onPressed: busy ? null : () => run(s, settings: true),
                  child: const Text('Abrir info de la app'),
                ),
              ],
            ),
          ),
      ],
      [
        FilledButton(
          key: ValueKey('guide-$primaryLabel'),
          onPressed: busy ? null : primary,
          style: FilledButton.styleFrom(backgroundColor: ready ? null : color),
          child: busy
              ? const Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                    SizedBox(width: 12),
                    Text('Un momento…'),
                  ],
                )
              : Text(primaryLabel),
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
      badge(
        ready == list.length ? Icons.celebration : Icons.fact_check_outlined,
        ready == list.length
            ? stateColor(context, 'ready')
            : Theme.of(context).colorScheme.primary,
      ),
      const SizedBox(height: 14),
      Text(
        ready == list.length ? '¡Tu teléfono está listo!' : 'Así quedó',
        style: Theme.of(
          context,
        ).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700),
        textAlign: TextAlign.center,
      ),
      const SizedBox(height: 8),
      Text(
        '$ready de ${list.length} pasos activos. Puedes volver a esta guía cuando quieras desde Inicio.',
        textAlign: TextAlign.center,
      ),
      const SizedBox(height: 12),
      for (var i = 0; i < list.length; i++)
        Builder(
          builder: (context) {
            final state = stepState(list[i], status, device, policy);
            final c = colorOf(list[i].kind);
            return Card(
              margin: const EdgeInsets.only(bottom: 8),
              child: ListTile(
                leading: CircleAvatar(
                  backgroundColor: c.withValues(alpha: 0.15),
                  child: Icon(list[i].icon, color: c),
                ),
                title: Text(list[i].title),
                subtitle: Text(
                  stateLabels[state] ?? state,
                  style: TextStyle(color: stateColor(context, state)),
                ),
                trailing: state == 'ready'
                    ? Icon(
                        Icons.check_circle,
                        color: stateColor(context, state),
                      )
                    : TextButton(
                        onPressed: () => go(i + 1),
                        child: const Text('Activar'),
                      ),
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

/// Recuadro de color con título e ítems (qué va a pasar, para qué sirve…).
class _Box extends StatelessWidget {
  const _Box({
    required this.color,
    required this.icon,
    required this.title,
    required this.items,
  });
  final Color color;
  final IconData icon;
  final String title;
  final List<String> items;
  @override
  Widget build(BuildContext context) => Container(
    margin: const EdgeInsets.only(bottom: 10),
    padding: const EdgeInsets.all(14),
    decoration: BoxDecoration(
      color: color.withValues(alpha: 0.08),
      borderRadius: BorderRadius.circular(16),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: Theme.of(context).textTheme.titleSmall?.copyWith(
            color: color,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 4),
        for (final item in items) _Bullet(icon: icon, text: item, color: color),
      ],
    ),
  );
}

class _Notice extends StatelessWidget {
  const _Notice({required this.color, required this.icon, required this.text});
  final Color color;
  final IconData icon;
  final String text;
  @override
  Widget build(BuildContext context) => Semantics(
    liveRegion: true,
    child: Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withValues(alpha: 0.4)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color),
          const SizedBox(width: 10),
          Expanded(child: Text(text)),
        ],
      ),
    ),
  );
}

class _Tile extends StatelessWidget {
  const _Tile({required this.color, required this.icon, required this.text});
  final Color color;
  final IconData icon;
  final String text;
  @override
  Widget build(BuildContext context) => Container(
    margin: const EdgeInsets.only(bottom: 10),
    padding: const EdgeInsets.all(14),
    decoration: BoxDecoration(
      color: color.withValues(alpha: 0.09),
      borderRadius: BorderRadius.circular(16),
    ),
    child: Row(
      children: [
        CircleAvatar(
          radius: 18,
          backgroundColor: color,
          child: Icon(icon, color: Colors.white, size: 20),
        ),
        const SizedBox(width: 12),
        Expanded(child: Text(text)),
      ],
    ),
  );
}

class _Bullet extends StatelessWidget {
  const _Bullet({required this.icon, required this.text, this.color});
  final IconData icon;
  final String text;
  final Color? color;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 4),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(top: 2),
          child: Icon(
            icon,
            size: icon == Icons.circle ? 8 : 18,
            color: color ?? Theme.of(context).colorScheme.primary,
          ),
        ),
        const SizedBox(width: 10),
        Expanded(child: Text(text)),
      ],
    ),
  );
}
