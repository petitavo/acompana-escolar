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
    home['capture_active'] = false;
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
      expect(find.text('Escribe el código que te dio tu colegio.'), findsOneWidget);
      expect(find.text('LAB · prueba interna con adultos'), findsNothing);
      expect(find.byKey(const ValueKey('code-field')), findsOneWidget);
      await expectLater(
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
    expect(find.text('Hola, Ana Ficticia'), findsOneWidget);
    await expectLater(
      find.byType(SchoolApp),
      matchesGoldenFile('goldens/product-home.png'),
    );
    await t.tap(find.text('Quiero que me contacten'));
    await t.pumpAndSettle();
    // Primero confirma, para no enviar pedidos por un toque accidental.
    expect(calls, isNot(contains('schoolSupport')));
    await t.tap(find.text('Sí, que me contacten'));
    await t.pumpAndSettle();
    expect(calls, contains('schoolSupport'));
    expect(
      find.textContaining('el equipo todavía no los recibió'),
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
    expect(find.text(instrument['recall']), findsOneWidget);
    expect(find.byType(RadioListTile<int>), findsNWidgets(36));
    expect(find.text('Enviar respuesta'), findsOneWidget);
    await expectLater(
      find.byType(SchoolApp),
      matchesGoldenFile('goldens/product-phq.png'),
    );
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
      await expectLater(
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
    // Tras aceptar, la guía de permisos se abre sola y no pide nada sin un toque.
    expect(find.text('Vamos a preparar tu teléfono'), findsOneWidget);
    expect(calls, isNot(contains('schoolPermission')));
    // Y desde esa guía sí se puede pedir un permiso (antes quedaba bloqueada).
    await t.tap(find.text('Empezar'));
    await t.pumpAndSettle();
    await t.tap(find.widgetWithText(FilledButton, 'Permitir'));
    await t.pumpAndSettle();
    expect(calls.where((x) => x == 'schoolPermission').length, 1);
    calls.removeWhere((x) => x == 'schoolPermission');
    await t.pageBack();
    await t.pumpAndSettle();
    expect(find.text('Permisos de este teléfono'), findsOneWidget);
    expect(find.text('Aceptar y continuar'), findsNothing);
    expect(calls.where((x) => x == 'schoolParticipation').length, 1);
    expect(calls, isNot(contains('schoolStartSensors')));
    expect(calls, isNot(contains('schoolPermission')));
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
  testWidgets('granting a permission does not resume a paused participation', (
    t,
  ) async {
    enrolled = true;
    await t.pumpWidget(const SchoolApp());
    await t.pumpAndSettle();
    await t.tap(find.text('Participación'));
    await t.pumpAndSettle();
    await t.tap(find.byKey(const ValueKey('permission-location')));
    await t.pumpAndSettle();
    expect(calls, contains('schoolPermission'));
    expect(calls, isNot(contains('schoolStartSensors')));
    expect(find.text('Participación pausada'), findsOneWidget);
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
    await t.tap(find.text('Abrir guía paso a paso'));
    await t.pumpAndSettle();
    expect(find.text('Vamos a preparar tu teléfono'), findsOneWidget);
    await t.tap(find.text('Empezar'));
    await t.pumpAndSettle();
    expect(find.text('Paso 1 de 5'), findsOneWidget);
    expect(find.textContaining('Lo que NO vemos'), findsWidgets);
    await expectLater(
      find.byType(SchoolApp),
      matchesGoldenFile('goldens/product-guide.png'),
    );
    await t.tap(find.widgetWithText(FilledButton, 'Permitir'));
    await t.pumpAndSettle();
    expect(calls, contains('schoolPermission'));
    expect(find.widgetWithText(FilledButton, 'Abrir ajustes'), findsOneWidget);
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
    expect(find.text('Prepara tu teléfono'), findsOneWidget);
    await t.tap(find.widgetWithText(FilledButton, 'Permitir'));
    await t.pumpAndSettle();
    // Guarda la preferencia y pide el permiso en el mismo toque, con la guía encima.
    expect(calls.where((x) => x == 'schoolParticipation').length, 1);
    expect(calls.where((x) => x == 'schoolPermission').length, 1);
    expect(locationGranted, isTrue);
    expect(find.text('¡Listo! Este paso ya está activo.'), findsOneWidget);
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
