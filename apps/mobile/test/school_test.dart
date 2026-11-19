import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:acompana_escolar/school.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  final instrument = jsonDecode(
    File('../../packages/contracts/fixtures/phq9.json').readAsStringSync(),
  );
  final calls = <String>[];
  bool enrolled = false, formsFail = false;
  String permissionState = 'granted';
  bool locationGranted = false, sensorRunning = false, policyPending = false;
  bool stepsGranted = false;
  String locationMode = 'precise';
  final deviceInfo = <String, dynamic>{};
  final starts = <dynamic>[];
  List<Map<String, dynamic>> deliveryLog = [];
  final home = {
    'name': 'Ana Ficticia',
    'is_test': true,
    'authorization': {
      'ready': true,
      'guardian': true,
      'student': true,
      'minor': true,
      'version': 'participacion-v1',
    },
    'capture_active': false,
    'pilot_enabled': true,
    'questionnaire_enabled': true,
    'policy': {
      'usage': false,
      'location': false,
      'steps': false,
      'reminders': true,
      'reminder_time': '17:00',
    },
    'document':
        'Información ficticia de participación para pruebas de la interfaz.',
    'purpose': 'Prueba de acompañamiento escolar.',
    'coverage': {
      'open': false,
      'text': 'Lunes a viernes, 08:00 a 17:00.',
      'resources': [
        {
          'title': 'Recurso ficticio de prueba',
          'contact': 'No contactar; prueba de interfaz',
        },
      ],
    },
  };
  setUpAll(() async {
    // Fuentes de los goldens: solo existen en Linux (CI).
    if (!Platform.isLinux) return;
    final font = FontLoader('Roboto');
    font.addFont(
      Future.value(
        ByteData.sublistView(
          File(
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
          ).readAsBytesSync(),
        ),
      ),
    );
    await font.load();
    final icons = FontLoader('MaterialIcons');
    icons.addFont(
      Future.value(
        ByteData.sublistView(
          File(
            '../../.tooling/flutter/bin/cache/artifacts/material_fonts/MaterialIcons-Regular.otf',
          ).readAsBytesSync(),
        ),
      ),
    );
    await icons.load();
  });
  setUp(() {
    enrolled = false;
    formsFail = false;
    permissionState = 'granted';
    locationGranted = false;
    stepsGranted = false;
    locationMode = 'precise';
    deviceInfo.clear();
    starts.clear();
    sensorRunning = false;
    policyPending = false;
    deliveryLog = [];
    calls.clear();
    (home['policy'] as Map<String, Object>).addAll({
      'usage': false,
      'location': false,
      'steps': false,
      'reminders': true,
    });
    // Ya aceptó: lo normal es que este teléfono esté participando.
    home['capture_active'] = true;
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
          const MethodChannel('pe.upc.acompana/collector'),
          (call) async {
            calls.add(call.method);
            switch (call.method) {
              case 'schoolStatus':
                return jsonEncode({
                  'enrolled': enrolled,
                  'mode': 'REAL',
                  'active': home['capture_active'],
                  'steps_supported': true,
                  'steps_permission': stepsGranted,
                  'location_permission': locationGranted
                      ? locationMode
                      : 'missing',
                  'sensor_running': sensorRunning,
                  'policy_pending': policyPending,
                  'home': home,
                  'outbox_pending': 0,
                  'last_sync': '2026-09-06T17:00:00Z',
                });
              case 'schoolHome':
                return jsonEncode(home);
              case 'schoolForms':
                if (formsFail) throw PlatformException(code: 'FORMS_OFFLINE');
                return jsonEncode([instrument]);
              case 'schoolDraft':
                return '{}';
              case 'schoolRequests':
                return '{"requests":[],"appointments":[]}';
              case 'schoolDeliveryLog':
                return jsonEncode(deliveryLog);
              case 'schoolDismiss':
                deliveryLog.removeWhere(
                  (e) =>
                      e['id'] == call.arguments['id'] &&
                      e['dismissible'] == true,
                );
                return '{"enrolled":true,"outbox_pending":0}';
              case 'schoolStartSensors':
                starts.add(call.arguments);
                sensorRunning = true;
                return jsonEncode({
                  'enrolled': true,
                  'active': true,
                  'sensor_running': true,
                  'steps_supported': true,
                  'steps_permission': stepsGranted,
                  'location_permission': locationGranted
                      ? locationMode
                      : 'missing',
                });
              case 'schoolPermission':
                if (permissionState == 'granted' &&
                    call.arguments['kind'] == 'location') {
                  locationGranted = true;
                }
                if (permissionState == 'granted' &&
                    call.arguments['kind'] == 'steps') {
                  stepsGranted = true;
                }
                return jsonEncode({'state': permissionState});
              case 'schoolParticipation':
                final body = jsonDecode(call.arguments['body']);
                if (!policyPending) {
                  for (final key in [
                    'usage',
                    'location',
                    'steps',
                    'reminders',
                  ]) {
                    (home['policy'] as Map)[key] = body[key];
                  }
                }
                (home['authorization'] as Map<String, Object>).addAll({
                  'student': true,
                  'ready': true,
                });
                if (body['action'] != 'preferences') {
                  home['capture_active'] = true;
                }
                return jsonEncode({
                  'enrolled': true,
                  'active': true,
                  'policy_pending': policyPending,
                  'decision_state': 'confirmed',
                  'home': home,
                });
              case 'schoolDeviceSetup':
                return jsonEncode(deviceInfo);
              case 'schoolOpenBattery':
                deviceInfo['battery_unrestricted'] = true;
                return '{"state":"granted"}';
              case 'schoolSupport':
                return '{"enrolled":true,"outbox_pending":1}';
              default:
                return '{}';
            }
          },
        );
  });
  testWidgets(
    'product onboarding separates verification and never claims sensors',
    (t) async {
      await t.binding.setSurfaceSize(const Size(390, 844));
      await t.pumpWidget(const SchoolApp());
      await t.pumpAndSettle();
      expect(
        find.text('Escribe el código que te dio tu colegio.'),
        findsOneWidget,
      );
      expect(find.text('LAB · prueba interna con adultos'), findsNothing);
      expect(find.byKey(const ValueKey('code-field')), findsOneWidget);
      if (Platform.isLinux) await expectLater(
        find.byType(SchoolApp),
        matchesGoldenFile('goldens/product-onboarding.png'),
      );
      await t.binding.setSurfaceSize(null);
    },
  );
  testWidgets('support available without GPS and explains offline receipt', (
    t,
  ) async {
    enrolled = true;
    await t.binding.setSurfaceSize(const Size(390, 844));
    await t.pumpWidget(const SchoolApp());
    await t.pumpAndSettle();
    expect(find.text('¡Hola, Ana!'), findsOneWidget);
    expect(find.text('Tu camino'), findsOneWidget);
    if (Platform.isLinux) await expectLater(
      find.byType(SchoolApp),
      matchesGoldenFile('goldens/product-home.png'),
    );
    await t.ensureVisible(find.text('Quiero que me contacten'));
    await t.pumpAndSettle();
    await t.tap(find.text('Quiero que me contacten'));
    await t.pumpAndSettle();
    // Primero confirma, para no enviar pedidos por un toque accidental.
    expect(calls, isNot(contains('schoolSupport')));
    await t.tap(find.text('Sí, que me contacten'));
    await t.pumpAndSettle();
    expect(calls, contains('schoolSupport'));
    expect(
      find.textContaining('Se enviará solo cuando haya internet'),
      findsOneWidget,
    );
    await t.binding.setSurfaceSize(null);
  });
  testWidgets(
    'A04: stale/rejected local items stay visible and can be dismissed',
    (t) async {
      enrolled = true;
      deliveryLog = [
        {
          'id': 'r1',
          'state': 'rejected',
          'kind': 'school_form',
          'label': 'Respuesta de cuestionario',
          'error': 'http_409',
          'dismissible': true,
          'category': 'form',
          'created_at': '2026-08-01T12:00:00Z',
        },
        {
          'id': 'p1',
          'state': 'pending',
          'kind': 'school_support',
          'label': 'Solicitud de acompañamiento',
          'error': '',
          'dismissible': false,
          'category': 'form',
          'created_at': '2026-08-20T12:00:00Z',
        },
        {
          'id': 'c1',
          'state': 'expired',
          'kind': 'event',
          'label': 'Datos de sensores',
          'error': 'capture_window_expired',
          'dismissible': true,
          'category': 'capture',
          'created_at': '2026-07-01T12:00:00Z',
        },
      ];
      await t.binding.setSurfaceSize(const Size(390, 900));
      addTearDown(() => t.binding.setSurfaceSize(null));
      await t.pumpWidget(const SchoolApp());
      await t.pumpAndSettle();
      await t.tap(find.text('Solicitudes'));
      await t.pumpAndSettle();
      expect(find.text('Estado de mis envíos'), findsOneWidget);
      expect(find.textContaining('Pendiente de envío'), findsOneWidget);
      expect(find.textContaining('ya había una respuesta'), findsOneWidget);
      expect(find.text('Descartar'), findsNWidgets(2)); // rejected + expired
      await t.tap(find.text('Descartar').first);
      await t.pumpAndSettle();
      expect(calls, contains('schoolDismiss'));
      expect(find.text('Descartar'), findsOneWidget); // one dismissed
      // the pending support item is never dismissible
      expect(find.textContaining('Pendiente de envío'), findsOneWidget);
    },
  );
  testWidgets('exact PHQ9 renders nine questions and source options', (
    t,
  ) async {
    enrolled = true;
    await t.binding.setSurfaceSize(const Size(390, 844));
    await t.pumpWidget(const SchoolApp());
    await t.pumpAndSettle();
    await t.tap(find.text('Cuestionario'));
    await t.pumpAndSettle();
    // Una pregunta por pantalla, con la instrucción del instrumento a la vista.
    expect(find.text(instrument['recall']), findsOneWidget);
    expect(find.text('Pregunta 1 de 9'), findsOneWidget);
    expect(find.text(instrument['questions'][0]['text']), findsOneWidget);
    for (final o in instrument['options']) {
      expect(find.text(o['label']), findsOneWidget);
    }
    expect(find.text('Enviar respuesta'), findsNothing);
    if (Platform.isLinux) await expectLater(
      find.byType(SchoolApp),
      matchesGoldenFile('goldens/product-phq.png'),
    );
    // Elegir "Varios días" en las 9 preguntas pasa solo a la siguiente; luego
    // aparece la pregunta de dificultad y al final "Enviar respuesta".
    for (var i = 0; i < 9; i++) {
      expect(find.text(instrument['questions'][i]['text']), findsOneWidget);
      final option = find.text(instrument['options'][1]['label']);
      await t.ensureVisible(option);
      await t.tap(option);
      await t.pump(const Duration(milliseconds: 300));
      await t.pumpAndSettle();
    }
    expect(find.text(instrument['functioning']['text']), findsOneWidget);
    final first = find.text(instrument['functioning']['options'][0]);
    await t.ensureVisible(first);
    await t.tap(first);
    await t.pump(const Duration(milliseconds: 300));
    await t.pumpAndSettle();
    expect(find.text('¡Respondiste todo!'), findsOneWidget);
    expect(find.text('Enviar respuesta'), findsOneWidget);
    await t.binding.setSurfaceSize(null);
  });
  testWidgets(
    'pending guardian explains blocked consent and cannot request permissions',
    (t) async {
      enrolled = true;
      final auth = home['authorization'] as Map<String, Object>;
      final previous = Map<String, Object>.from(auth);
      addTearDown(() {
        auth
          ..clear()
          ..addAll(previous);
      });
      auth.addAll({'guardian': false, 'student': false, 'ready': false});
      await t.binding.setSurfaceSize(const Size(390, 844));
      addTearDown(() => t.binding.setSurfaceSize(null));
      await t.pumpWidget(const SchoolApp());
      await t.pumpAndSettle();
      await t.tap(find.text('Participación'));
      await t.pumpAndSettle();
      expect(find.textContaining('Falta la autorización'), findsOneWidget);
      expect(find.text('Comprobar autorización'), findsNothing);
      await t.scrollUntilVisible(
        find.text('Pendiente de autorización del responsable'),
        350,
        scrollable: find.byType(Scrollable).first,
      );
      final button = t.widget<FilledButton>(
        find.widgetWithText(
          FilledButton,
          'Pendiente de autorización del responsable',
        ),
      );
      expect(button.onPressed, isNull);
      expect(find.byKey(const ValueKey('permission-location')), findsNothing);
      expect(calls, isNot(contains('schoolPermission')));
      expect(calls, isNot(contains('schoolParticipation')));
    },
  );
  testWidgets(
    'confirmed authorization remains visible if questionnaire refresh fails',
    (t) async {
      enrolled = true;
      formsFail = true;
      await t.binding.setSurfaceSize(const Size(390, 844));
      addTearDown(() => t.binding.setSurfaceSize(null));
      await t.pumpWidget(const SchoolApp());
      await t.pumpAndSettle();
      await t.tap(find.text('Participación'));
      await t.pumpAndSettle();
      expect(find.text('Permisos de este teléfono'), findsOneWidget);
      expect(find.text('Permisos de este teléfono'), findsOneWidget);
      expect(find.text('Aceptar y continuar'), findsNothing);
      expect(calls, isNot(contains('schoolParticipation')));
    },
  );

  testWidgets(
    'denied Android permission explains outcome without starting sensors',
    (t) async {
      enrolled = true;
      permissionState = 'denied';
      final policy = home['policy'] as Map<String, Object>;
      policy['location'] = true;
      addTearDown(() => policy['location'] = false);
      await t.binding.setSurfaceSize(const Size(390, 844));
      addTearDown(() => t.binding.setSurfaceSize(null));
      await t.pumpWidget(const SchoolApp());
      await t.pumpAndSettle();
      await t.tap(find.text('Participación'));
      await t.pumpAndSettle();
      await t.scrollUntilVisible(
        find.byKey(const ValueKey('permission-location')),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await t.tap(find.byKey(const ValueKey('permission-location')));
      await t.pumpAndSettle();
      expect(find.textContaining('Permiso no concedido.'), findsOneWidget);
      if (Platform.isLinux) await expectLater(
        find.byType(SchoolApp),
        matchesGoldenFile('goldens/product-participation.png'),
      );
      expect(calls, contains('schoolPermission'));
      expect(calls, isNot(contains('schoolStartSensors')));
    },
  );

  testWidgets('accepted participation moves to confirmed permission controls', (
    t,
  ) async {
    enrolled = true;
    final auth = home['authorization'] as Map<String, Object>;
    final previous = Map<String, Object>.from(auth);
    addTearDown(() {
      auth
        ..clear()
        ..addAll(previous);
      home['capture_active'] = false;
    });
    auth.addAll({'student': false, 'ready': false});
    home['capture_active'] = false;
    await t.binding.setSurfaceSize(const Size(390, 844));
    addTearDown(() => t.binding.setSurfaceSize(null));
    await t.pumpWidget(const SchoolApp());
    await t.pumpAndSettle();
    await t.tap(find.text('Participación'));
    await t.pumpAndSettle();
    final check = find.byType(CheckboxListTile);
    await t.scrollUntilVisible(
      check,
      200,
      scrollable: find.byType(Scrollable).first,
    );
    await t.tap(check);
    await t.pumpAndSettle();
    await t.scrollUntilVisible(
      find.text('Aceptar y continuar'),
      250,
      scrollable: find.byType(Scrollable).first,
    );
    await t.tap(find.text('Aceptar y continuar'));
    await t.pumpAndSettle();
    // Tras aceptar vuelve a Inicio: el paso 2 (preparar el teléfono) queda marcado
    // y nada se abre solo.
    expect(find.text('Tu camino'), findsOneWidget);
    expect(find.textContaining('Sigue con el paso 2'), findsOneWidget);
    expect(find.text('Activa los permisos'), findsNothing);
    expect(calls, isNot(contains('schoolPermission')));
    // Desde Inicio, un botón abre la pantalla de permisos y otro los pide todos.
    await t.tap(find.text('Activar permisos'));
    await t.pumpAndSettle();
    expect(find.text('Activa los permisos'), findsOneWidget);
    expect(calls, isNot(contains('schoolPermission')));
    await t.tap(find.byKey(const ValueKey('guide-main')));
    await t.pumpAndSettle();
    // Una sola vez al servidor (aceptar + guardar todo) y luego las ventanas seguidas.
    expect(calls.where((x) => x == 'schoolParticipation').length, 2);
    expect(calls.where((x) => x == 'schoolPermission').length, greaterThan(1));
    expect(locationGranted, isTrue);
    expect(stepsGranted, isTrue);
    // Se detiene antes de "Ubicación siempre", que abre Ajustes, y dice qué tocar.
    expect(find.textContaining('Permitir todo el tiempo'), findsOneWidget);
    await t.pageBack();
    await t.pumpAndSettle();
    expect(find.text('Tu camino'), findsOneWidget);
    expect(find.text('Aceptar y continuar'), findsNothing);
  });
  testWidgets(
    'one tap saves selection, requests Android and starts granted sensors',
    (t) async {
      enrolled = true;
      home['capture_active'] = true;
      await t.pumpWidget(const SchoolApp());
      await t.pumpAndSettle();
      await t.tap(find.text('Participación'));
      await t.pumpAndSettle();
      await t.tap(find.byKey(const ValueKey('permission-location')));
      await t.pumpAndSettle();
      expect(calls.where((v) => v == 'schoolParticipation').length, 1);
      expect(calls.where((v) => v == 'schoolPermission').length, 1);
      expect(calls, contains('schoolStartSensors'));
      expect(find.byKey(const ValueKey('permission-location')), findsNothing);
      expect(find.text('Activo'), findsOneWidget);
      expect(find.text('Iniciar sensores autorizados'), findsNothing);
    },
  );

  testWidgets(
    'offline choice never requests Android before server confirmation',
    (t) async {
      enrolled = true;
      policyPending = true;
      await t.pumpWidget(const SchoolApp());
      await t.pumpAndSettle();
      await t.tap(find.text('Participación'));
      await t.pumpAndSettle();
      final button = t.widget<TextButton>(
        find.byKey(const ValueKey('permission-location')),
      );
      expect(button.onPressed, isNull);
      expect(calls, isNot(contains('schoolPermission')));
    },
  );

  testWidgets('questionnaire has one tab and refreshes when opened', (t) async {
    enrolled = true;
    await t.pumpWidget(const SchoolApp());
    await t.pumpAndSettle();
    expect(find.text('Revisar cuestionario'), findsNothing);
    final before = calls.where((v) => v == 'schoolForms').length;
    await t.tap(find.text('Cuestionario'));
    await t.pumpAndSettle();
    expect(calls.where((v) => v == 'schoolForms').length, greaterThan(before));
    expect(find.text('Cómo te has sentido'), findsOneWidget);
  });
  testWidgets('a stopped phone resumes by itself and offers no pause', (
    t,
  ) async {
    // Código renovado o versión anterior que pausó: ya aceptó, así que sigue
    // participando sin que el alumno tenga que tocar "Reanudar".
    enrolled = true;
    home['capture_active'] = false;
    await t.pumpWidget(const SchoolApp());
    await t.pumpAndSettle();
    expect(calls.where((c) => c == 'schoolParticipation').length, 1);
    expect(home['capture_active'], isTrue);
    await t.tap(find.text('Participación'));
    await t.pumpAndSettle();
    expect(find.text('Participación pausada'), findsNothing);
    expect(find.text('Pausar'), findsNothing);
    expect(find.text('Reanudar'), findsNothing);
    expect(calls.where((c) => c == 'schoolParticipation').length, 1);
  });
  testWidgets(
    'new step permission refreshes an already running location service',
    (t) async {
      enrolled = true;
      home['capture_active'] = true;
      (home['policy'] as Map)['location'] = true;
      locationGranted = true;
      sensorRunning = true;
      await t.pumpWidget(const SchoolApp());
      await t.pumpAndSettle();
      await t.tap(find.text('Participación'));
      await t.pumpAndSettle();
      starts.clear();
      final button = find.byKey(const ValueKey('permission-steps'));
      await t.ensureVisible(button);
      await t.tap(button);
      await t.pumpAndSettle();
      expect(stepsGranted, isTrue);
      expect(starts.last['reconfigure'], isTrue);
      expect(find.byKey(const ValueKey('permission-steps')), findsNothing);
    },
  );
  testWidgets(
    'returning from Android settings refreshes permissions and running sensors',
    (t) async {
      enrolled = true;
      home['capture_active'] = true;
      (home['policy'] as Map<String, Object>).addAll({
        'location': true,
        'steps': true,
      });
      locationGranted = true;
      sensorRunning = true;
      await t.pumpWidget(const SchoolApp());
      await t.pumpAndSettle();
      await t.tap(find.text('Participación'));
      await t.pumpAndSettle();
      starts.clear();
      t.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
      stepsGranted = true;
      t.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await t.pumpAndSettle();
      expect(starts.last['reconfigure'], isTrue);
      expect(find.byKey(const ValueKey('permission-steps')), findsNothing);
    },
  );

  testWidgets('guide explains each step and offers settings when blocked', (
    t,
  ) async {
    enrolled = true;
    home['capture_active'] = true;
    permissionState = 'blocked';
    await t.binding.setSurfaceSize(const Size(390, 844));
    addTearDown(() => t.binding.setSurfaceSize(null));
    await t.pumpWidget(const SchoolApp());
    await t.pumpAndSettle();
    await t.tap(find.text('Participación'));
    await t.pumpAndSettle();
    await t.ensureVisible(find.text('Activar permisos'));
    await t.pumpAndSettle();
    await t.tap(find.text('Activar permisos'));
    await t.pumpAndSettle();
    expect(find.text('Activa los permisos'), findsOneWidget);
    expect(find.text('Uso de pantalla'), findsOneWidget);
    if (Platform.isLinux) await expectLater(
      find.byType(SchoolApp),
      matchesGoldenFile('goldens/product-guide.png'),
    );
    await t.tap(find.byKey(const ValueKey('guide-main')));
    await t.pumpAndSettle();
    expect(calls, contains('schoolPermission'));
    // Lo que Android ya no deja pedir queda marcado y se abre Ajustes al tocarlo.
    expect(find.textContaining('Bloqueado'), findsWidgets);
    await t.tap(find.byKey(const ValueKey('guide-row-location')));
    await t.pumpAndSettle();
    expect(calls, contains('schoolOpenSettings'));
    expect(calls, isNot(contains('schoolStartSensors')));
  });

  testWidgets('approximate location asks for precise location for attendance', (
    t,
  ) async {
    enrolled = true;
    home['capture_active'] = true;
    (home['policy'] as Map)['location'] = true;
    locationGranted = true;
    locationMode = 'approximate';
    await t.pumpWidget(const SchoolApp());
    await t.pumpAndSettle();
    await t.tap(find.text('Participación'));
    await t.pumpAndSettle();
    expect(find.text('Solo aproximada'), findsOneWidget);
    expect(find.text('Usar precisa'), findsOneWidget);
  });

  testWidgets('autostart step only appears on brands that need it', (t) async {
    enrolled = true;
    home['capture_active'] = true;
    deviceInfo.addAll({'manufacturer': 'xiaomi', 'autostart_screen': true});
    await t.pumpWidget(const SchoolApp());
    await t.pumpAndSettle();
    await t.tap(find.text('Participación'));
    await t.pumpAndSettle();
    expect(find.byKey(const ValueKey('permission-autostart')), findsOneWidget);
    deviceInfo
      ..clear()
      ..addAll({'manufacturer': 'samsung'});
    await t.pumpWidget(const SizedBox());
    await t.pumpWidget(const SchoolApp());
    await t.pumpAndSettle();
    await t.tap(find.text('Participación'));
    await t.pumpAndSettle();
    expect(find.byKey(const ValueKey('permission-autostart')), findsNothing);
  });

  test('invitation link or plain code are both accepted', () {
    final link = parseInvitation('https://x.pe/app?inv=abc123', 'https://otro');
    expect(link.token, 'abc123');
    expect(link.server, 'https://x.pe');
    final plain = parseInvitation('  abc123 ', 'https://otro');
    expect(plain.token, 'abc123');
    expect(plain.server, 'https://otro');
  });

  test('phone numbers in help resources become callable', () {
    expect(phoneIn('Línea 113, opción 5'), '113');
    expect(phoneIn('Llama al 0800-10828 gratis'), '080010828');
    expect(phoneIn('Escríbenos por la web'), isNull);
  });

  testWidgets('guide grants a not-yet-shared permission with a single tap', (
    t,
  ) async {
    enrolled = true;
    home['capture_active'] = true;
    await t.binding.setSurfaceSize(const Size(390, 844));
    addTearDown(() => t.binding.setSurfaceSize(null));
    await t.pumpWidget(const SchoolApp());
    await t.pumpAndSettle();
    await t.tap(find.text('Participación'));
    await t.pumpAndSettle();
    await t.tap(find.text('Ubicación'));
    await t.pumpAndSettle();
    // Un toque: guarda la preferencia y pide solo ese permiso.
    expect(find.text('Activa los permisos'), findsOneWidget);
    expect(calls.where((x) => x == 'schoolParticipation').length, 1);
    expect(calls.where((x) => x == 'schoolPermission').length, 1);
    expect(locationGranted, isTrue);
    expect(
      find.descendant(
        of: find.byKey(const ValueKey('guide-row-location')),
        matching: find.text('Activo'),
      ),
      findsOneWidget,
    );
  });

  testWidgets('a single access code links the phone', (t) async {
    Map? enrollArgs;
    await t.pumpWidget(const SchoolApp());
    await t.pumpAndSettle();
    t.binding.defaultBinaryMessenger.setMockMethodCallHandler(
      const MethodChannel('pe.upc.acompana/collector'),
      (call) async {
        calls.add(call.method);
        if (call.method == 'schoolEnroll') {
          enrollArgs = Map.from(call.arguments);
        }
        return '{"enrolled":false}';
      },
    );
    // Versión de prueba sin servidor fijo: además pide la dirección.
    await t.enterText(find.byKey(const ValueKey('code-field')), 'abcd-2345');
    await t.enterText(find.byType(TextField).last, 'https://colegio.example');
    await t.pumpAndSettle();
    await t.tap(find.text('Entrar'));
    await t.pumpAndSettle();
    expect(enrollArgs?['invitation'], 'ABCD2345');
    expect(enrollArgs?['server'], 'https://colegio.example');
    expect(enrollArgs?['code'], '');
  });
}
