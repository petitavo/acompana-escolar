# Acompaña Escolar

Aplicación escolar con Android/Flutter, panel web, FastAPI, PostgreSQL y procesamiento periódico. Proyecto independiente de SMCBackend. La experiencia principal permite incorporación y autorizaciones, PHQ-9 en español, solicitud de apoyo, citas, seguimiento profesional y participación con sensores opcionales.

## Probar en esta máquina

```bash
cd /home/petitavo/acompana-escolar
make product
```

Abre **http://127.0.0.1:5174/**. Si ya está iniciado, basta abrir el enlace. Acceso administrativo en `.runtime/credentials-product.json` (archivo privado, no incluido en Git). El asistente configura institución, responsables, cobertura y documentos. Crea estudiantes de prueba para evaluar los recorridos; el piloto real permanece desactivado. `make product-stop` detiene únicamente este entorno.

- [Guía de uso, instalación Android y operación](docs/producto.md).
- [Entrega, pruebas y dependencias pendientes](docs/ENTREGA-PRODUCTO.md).
- [Matriz del complemento](docs/MATRIZ-PRODUCTO.md).
- [Datos, modelos y límites de evaluación](docs/modelos-producto.md).
- [Herramientas DEMO/LAB conservadas](docs/laboratorio.md): puertos y datos separados; la demo anterior sigue en 5173.

El software de análisis y modelos está implementado; no hay un modelo clínico entrenado con datos reales autorizado para este colegio. No se ha publicado en internet ni activado captación de menores. La verificación física de sensores requiere un Android conectado.
