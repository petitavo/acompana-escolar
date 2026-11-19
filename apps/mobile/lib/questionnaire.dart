import 'package:flutter/material.dart';

/// Colores de la guía de estilo (Fig. 14): teal para acciones, tinta para texto.
const _teal = Color(0xff0e7c7b);
const _ink = Color(0xff173b4b);
const _muted = Color(0xff6d8390);
const _tealSoft = Color(0xffe3f2f0);
const _line = Color(0xffe0e9ed);
const _green = Color(0xff15803d);

const _planColors = {
  'PHQ9': Color(0xff0e7c7b),
  'PHQ2_SEMANAL': Color(0xff7c6cf2),
  'CONTACTO_DIARIO': Color(0xffff7a59),
  'CONTEXTO_MENSUAL': Color(0xfff59e0b),
};

const _planIcons = {
  'PHQ9': Icons.favorite_outline,
  'PHQ2_SEMANAL': Icons.bolt_outlined,
  'CONTACTO_DIARIO': Icons.chat_bubble_outline,
  'CONTEXTO_MENSUAL': Icons.groups_outlined,
};

/// Unos 15 segundos por pregunta.
String minutesFor(int questions) =>
    questions <= 3 ? 'menos de 1 min' : '≈ ${(questions * 15 / 60).ceil()} min';

String everyText(int days) => switch (days) {
  1 => 'cada día',
  7 => 'cada semana',
  14 => 'cada 2 semanas',
  >= 28 => 'cada mes',
  _ => 'cada $days días',
};

String shortDate(dynamic value) {
  final d = DateTime.tryParse('${value ?? ''}')?.toLocal();
  if (d == null) return '';
  const days = ['lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom'];
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
  final today = DateTime.now();
  final diff = DateTime(
    d.year,
    d.month,
    d.day,
  ).difference(DateTime(today.year, today.month, today.day)).inDays;
  if (diff <= 0) return 'hoy';
  if (diff == 1) return 'mañana';
  return '${days[d.weekday - 1]} ${d.day} ${months[d.month - 1]}';
}

String sinceText(dynamic value) {
  final d = shortDate(value);
  return d == 'hoy' || d == 'mañana' ? 'Desde $d' : 'Desde el $d';
}

/// Estado de un ítem del plan: 'now' (disponible), 'after' (después del actual) o 'later'.
String planState(Map item, Map? form) {
  final code = '${item['code']}';
  final current = form == null
      ? null
      : (form['functioning'] != null ? 'PHQ9' : '${form['instrument_id']}');
  if (code == current) return 'now';
  if (item['after_phq9'] == true) return 'after';
  if (item['next_at'] == null) return form == null ? 'now' : 'after';
  return 'later';
}

/// Lista "Lo que te toca": qué es, cuántas preguntas, cada cuánto y cuándo.
class PlanList extends StatelessWidget {
  const PlanList({super.key, required this.plan, this.form});
  final List plan;
  final Map? form;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      for (final (i, raw) in plan.indexed)
        Builder(
          builder: (context) {
            final item = Map.from(raw as Map);
            final code = '${item['code']}';
            final color = _planColors[code] ?? _teal;
            final st = planState(item, form);
            final n = (item['questions'] ?? 1) as int;
            return TweenAnimationBuilder<double>(
              tween: Tween(begin: 0, end: 1),
              duration: Duration(milliseconds: 300 + i * 80),
              curve: Curves.easeOutCubic,
              builder: (_, v, c) => Opacity(
                opacity: v,
                child: Transform.translate(
                  offset: Offset(0, 16 * (1 - v)),
                  child: c,
                ),
              ),
              child: Container(
                margin: const EdgeInsets.only(bottom: 10),
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: st == 'now' ? color.withValues(alpha: 0.08) : null,
                  border: Border.all(
                    color: st == 'now' ? color : _line,
                    width: st == 'now' ? 2 : 1,
                  ),
                  borderRadius: BorderRadius.circular(18),
                ),
                child: Row(
                  children: [
                    Container(
                      width: 44,
                      height: 44,
                      decoration: BoxDecoration(
                        color: color.withValues(alpha: 0.14),
                        borderRadius: BorderRadius.circular(14),
                      ),
                      child: Icon(_planIcons[code], color: color),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            '${item['title']}',
                            style: const TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w700,
                              color: _ink,
                            ),
                          ),
                          Text(
                            '$n ${n == 1 ? 'pregunta' : 'preguntas'} · ${everyText((item['every_days'] ?? 14) as int)}',
                            style: const TextStyle(color: _muted),
                          ),
                        ],
                      ),
                    ),
                    _Chip(
                      text: switch (st) {
                        'now' => 'Ahora',
                        'after' => 'Después',
                        _ => shortDate(item['next_at']),
                      },
                      color: st == 'now' ? color : _muted,
                      filled: st == 'now',
                    ),
                  ],
                ),
              ),
            );
          },
        ),
    ],
  );
}

class _Chip extends StatelessWidget {
  const _Chip({required this.text, required this.color, this.filled = false});
  final String text;
  final Color color;
  final bool filled;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
    decoration: BoxDecoration(
      color: filled ? color : color.withValues(alpha: 0.1),
      borderRadius: BorderRadius.circular(20),
    ),
    child: Text(
      text,
      style: TextStyle(
        color: filled ? Colors.white : color,
        fontSize: 12,
        fontWeight: FontWeight.w700,
      ),
    ),
  );
}

/// "Así funciona": aparece al terminar de activar los permisos, antes de responder
/// por primera vez. Explica qué viene primero, qué después y cuándo vuelve.
class PlanIntro extends StatelessWidget {
  const PlanIntro({super.key, required this.plan, this.form});
  final List plan;
  final Map? form;

  @override
  Widget build(BuildContext context) {
    final items = plan.map((e) => Map.from(e as Map)).toList();
    final first = items.where((i) => planState(i, form) == 'now').firstOrNull;
    final rest = items.where((i) => i != first).toList();
    return Scaffold(
      backgroundColor: const Color(0xfff4f7fb),
      body: Column(
        children: [
          Container(
            width: double.infinity,
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [Color(0xff0e7c7b), Color(0xff6d5df5)],
              ),
              borderRadius: BorderRadius.vertical(bottom: Radius.circular(32)),
            ),
            child: const SafeArea(
              bottom: false,
              child: Padding(
                padding: EdgeInsets.fromLTRB(8, 4, 20, 24),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    BackButton(color: Colors.white),
                    Padding(
                      padding: EdgeInsets.only(left: 12),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            '¡Tu teléfono está listo!',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 26,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          SizedBox(height: 6),
                          Text(
                            'Así funciona: respondes preguntas cortas y solo el equipo de psicología las ve.',
                            style: TextStyle(color: Colors.white, fontSize: 15),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 20, 16, 8),
              children: [
                if (first != null) ...[
                  _Step(
                    index: 1,
                    label: 'Primero',
                    item: first,
                    highlight: true,
                  ),
                ],
                for (final (i, item) in rest.indexed)
                  _Step(
                    index: i + (first == null ? 1 : 2),
                    label: planState(item, form) == 'later'
                        ? sinceText(item['next_at'])
                        : 'Después',
                    item: item,
                  ),
                const SizedBox(height: 8),
                const Text(
                  'Te avisaremos cuando te toque. No hay respuestas buenas ni malas.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: _muted),
                ),
              ],
            ),
          ),
          SafeArea(
            top: false,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
              child: FilledButton(
                style: FilledButton.styleFrom(
                  backgroundColor: _teal,
                  minimumSize: const Size.fromHeight(56),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(18),
                  ),
                ),
                onPressed: () => Navigator.of(context).pop(first != null),
                child: Text(
                  first != null ? 'Empezar ahora' : 'Entendido',
                  style: const TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _Step extends StatelessWidget {
  const _Step({
    required this.index,
    required this.label,
    required this.item,
    this.highlight = false,
  });
  final int index;
  final String label;
  final Map item;
  final bool highlight;
  @override
  Widget build(BuildContext context) {
    final code = '${item['code']}';
    final color = _planColors[code] ?? _teal;
    final n = (item['questions'] ?? 1) as int;
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: 1),
      duration: Duration(milliseconds: 350 + index * 120),
      curve: Curves.easeOutCubic,
      builder: (_, v, c) => Opacity(
        opacity: v,
        child: Transform.translate(offset: Offset(30 * (1 - v), 0), child: c),
      ),
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: highlight ? color : Colors.transparent,
            width: 2,
          ),
          boxShadow: [
            BoxShadow(
              color: const Color(0xff0f172a).withValues(alpha: 0.06),
              blurRadius: 10,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            CircleAvatar(
              radius: 18,
              backgroundColor: color,
              child: Text(
                '$index',
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    label.toUpperCase(),
                    style: TextStyle(
                      color: color,
                      fontSize: 12,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 0.8,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    '${item['title']}',
                    style: const TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.w700,
                      color: _ink,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    '$n ${n == 1 ? 'pregunta' : 'preguntas'} · ${minutesFor(n)} · ${everyText((item['every_days'] ?? 14) as int)}',
                    style: const TextStyle(color: _muted),
                  ),
                  const SizedBox(height: 6),
                  Text('${item['why'] ?? ''}'),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Cuestionario como en los mockups (M05/M06): una pregunta por pantalla,
/// "Pregunta X de N", instrucción en gris arriba, pregunta grande y opciones
/// en recuadros que se marcan en teal. Al elegir pasa sola a la siguiente.
class QuestionFlow extends StatefulWidget {
  const QuestionFlow({
    super.key,
    required this.title,
    required this.instructions,
    required this.questions,
    required this.answers,
    required this.onAnswer,
    required this.onSubmit,
    required this.busy,
    this.extra,
  });

  final String title;
  final String instructions;

  /// Cada pregunta: {id, text, options: [{value, label}]}.
  final List<Map> questions;
  final Map answers;
  final void Function(String id, int value) onAnswer;
  final VoidCallback? onSubmit;
  final bool busy;

  /// Pregunta adicional (funcionamiento del PHQ-9) cuando corresponde.
  final Map? extra;

  @override
  State<QuestionFlow> createState() => _QuestionFlowState();
}

class _QuestionFlowState extends State<QuestionFlow> {
  int page = 0;
  bool forward = true;

  List<Map> get all => [
    ...widget.questions,
    if (widget.extra != null) widget.extra!,
  ];

  @override
  void initState() {
    super.initState();
    // Si hay un borrador, continúa en la primera pregunta sin responder.
    final i = all.indexWhere((q) => widget.answers[q['id']] == null);
    page = i < 0 ? all.length : i;
  }

  void go(int i) => setState(() {
    forward = i > page;
    page = i.clamp(0, all.length);
  });

  void choose(Map q, int v) {
    widget.onAnswer('${q['id']}', v);
    final index = page;
    Future.delayed(const Duration(milliseconds: 260), () {
      if (mounted && page == index) go(page + 1);
    });
  }

  @override
  Widget build(BuildContext context) {
    final list = all;
    final total = list.length;
    final review = page >= total;
    final answered = list.where((q) => widget.answers[q['id']] != null).length;
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(24),
        boxShadow: [
          BoxShadow(
            color: const Color(0xff0f172a).withValues(alpha: 0.06),
            blurRadius: 14,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            padding: const EdgeInsets.fromLTRB(20, 18, 20, 16),
            color: _teal,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  widget.title,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 18,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 10),
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        review
                            ? 'Listo para enviar'
                            : page >= widget.questions.length
                            ? 'Una última pregunta'
                            : 'Pregunta ${page + 1} de ${widget.questions.length}',
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      review
                          ? '$answered/$total'
                          : page == total - 1
                          ? 'Última'
                          : minutesFor(total - page),
                      style: const TextStyle(color: Colors.white70),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                ClipRRect(
                  borderRadius: BorderRadius.circular(6),
                  child: TweenAnimationBuilder<double>(
                    tween: Tween(end: total == 0 ? 0 : answered / total),
                    duration: const Duration(milliseconds: 400),
                    curve: Curves.easeOutCubic,
                    builder: (_, v, _) => LinearProgressIndicator(
                      value: v,
                      minHeight: 8,
                      color: Colors.white,
                      backgroundColor: Colors.white24,
                    ),
                  ),
                ),
              ],
            ),
          ),
          AnimatedSwitcher(
            duration: const Duration(milliseconds: 280),
            transitionBuilder: (c, a) => FadeTransition(
              opacity: a,
              child: SlideTransition(
                position: Tween(
                  begin: Offset(forward ? 0.15 : -0.15, 0),
                  end: Offset.zero,
                ).animate(a),
                child: c,
              ),
            ),
            child: KeyedSubtree(
              key: ValueKey(page),
              child: review ? reviewPage(list) : questionPage(list[page]),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
            child: Row(
              children: [
                if (page > 0)
                  Expanded(
                    child: OutlinedButton(
                      style: OutlinedButton.styleFrom(
                        minimumSize: const Size.fromHeight(52),
                        foregroundColor: _teal,
                        side: const BorderSide(color: _teal, width: 1.5),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(16),
                        ),
                      ),
                      onPressed: widget.busy ? null : () => go(page - 1),
                      child: const Text('Anterior'),
                    ),
                  ),
                if (page > 0) const SizedBox(width: 12),
                Expanded(
                  child: FilledButton(
                    style: FilledButton.styleFrom(
                      minimumSize: const Size.fromHeight(52),
                      backgroundColor: _teal,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(16),
                      ),
                    ),
                    onPressed: widget.busy
                        ? null
                        : review
                        ? (answered == total ? widget.onSubmit : null)
                        : widget.answers[list[page]['id']] == null
                        ? null
                        : () => go(page + 1),
                    child: Text(review ? 'Enviar respuesta' : 'Siguiente'),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget questionPage(Map q) => Padding(
    padding: const EdgeInsets.fromLTRB(20, 18, 20, 16),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (q != widget.extra && widget.instructions.isNotEmpty)
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: _tealSoft,
              borderRadius: BorderRadius.circular(14),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(Icons.info_outline, color: _teal, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    widget.instructions,
                    style: const TextStyle(color: _ink, fontSize: 14),
                  ),
                ),
              ],
            ),
          ),
        const SizedBox(height: 16),
        Text(
          '${q['text']}',
          style: const TextStyle(
            color: _ink,
            fontSize: 22,
            height: 1.25,
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: 16),
        for (final o in (q['options'] as List)) option(q, Map.from(o as Map)),
      ],
    ),
  );

  Widget option(Map q, Map o) {
    final selected = widget.answers[q['id']] == o['value'];
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: widget.busy ? null : () => choose(q, o['value'] as int),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 15),
            decoration: BoxDecoration(
              color: selected ? _tealSoft : Colors.white,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: selected ? _teal : _line,
                width: selected ? 2 : 1.5,
              ),
            ),
            child: Row(
              children: [
                AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  width: 24,
                  height: 24,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: selected ? _teal : Colors.white,
                    border: Border.all(
                      color: selected ? _teal : const Color(0xff94a3b8),
                      width: 2,
                    ),
                  ),
                  child: selected
                      ? const Icon(Icons.check, size: 16, color: Colors.white)
                      : null,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    '${o['label']}',
                    style: TextStyle(
                      fontSize: 16,
                      color: _ink,
                      fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget reviewPage(List<Map> list) {
    final missing = list.indexWhere((q) => widget.answers[q['id']] == null);
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 24, 20, 20),
      child: Column(
        children: [
          TweenAnimationBuilder<double>(
            tween: Tween(begin: 0.6, end: 1),
            duration: const Duration(milliseconds: 500),
            curve: Curves.elasticOut,
            builder: (_, v, c) => Transform.scale(scale: v, child: c),
            child: CircleAvatar(
              radius: 34,
              backgroundColor: missing < 0 ? _green : const Color(0xffd97706),
              child: Icon(
                missing < 0 ? Icons.check_rounded : Icons.priority_high,
                color: Colors.white,
                size: 38,
              ),
            ),
          ),
          const SizedBox(height: 14),
          Text(
            missing < 0
                ? '¡Respondiste todo!'
                : 'Te falta la pregunta ${missing + 1}',
            style: const TextStyle(
              color: _ink,
              fontSize: 20,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            missing < 0
                ? 'Toca "Enviar respuesta". Solo el equipo de psicología lo verá.'
                : 'Vuelve a esa pregunta para terminar.',
            textAlign: TextAlign.center,
            style: const TextStyle(color: _muted),
          ),
          if (missing >= 0)
            TextButton(
              onPressed: () => go(missing),
              child: Text('Ir a la pregunta ${missing + 1}'),
            ),
        ],
      ),
    );
  }
}
