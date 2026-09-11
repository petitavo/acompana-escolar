import 'dart:convert';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:acompana_escolar/main.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
          const MethodChannel('pe.upc.acompana/collector'),
          (call) async => jsonEncode({
            'enrolled': false,
            'mode': 'LAB',
            'outbox_pending': 0,
          }),
        );
  });
  testWidgets(
    'onboarding explains consent and does not claim capture before enrollment',
    (tester) async {
      await tester.pumpWidget(const LaboratoryApp());
      await tester.pumpAndSettle();
      expect(find.text('Bienvenido al laboratorio'), findsOneWidget);
      expect(find.text('Vincular mi teléfono'), findsOneWidget);
      expect(find.text('Capturar ahora'), findsNothing);
    },
  );
}
