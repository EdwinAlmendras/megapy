# MEGA API Request Batching

## Introducción

La API de MEGA puede recibir múltiples requests en una sola llamada HTTP, lo que se conoce como "batching" o "agrupación de requests". Este sistema es crucial para evitar errores `EAGAIN (-3)` que ocurren cuando se hacen demasiadas llamadas API simultáneas.

## ¿Por qué es necesario el batching?

Cuando se suben múltiples archivos o se realizan muchas operaciones API simultáneamente, MEGA puede responder con el error:

```
EAGAIN (-3): A temporary congestion or server malfunction prevented your request 
from being processed. No data was altered.
```

Este error indica que el servidor está temporalmente congestionado debido a demasiadas solicitudes concurrentes. El batching resuelve esto agrupando múltiples requests en una sola llamada HTTP.

## Cómo funciona el batching en megapy

### Sistema de cola automática

El `AsyncAPIClient` implementa un sistema de batching automático similar al webclient oficial de MEGA:

1. **Cola de requests**: Los requests se agregan automáticamente a una cola interna
2. **Delay de 350ms**: Espera 350ms antes de enviar el batch (igual que el webclient)
3. **Batch máximo**: Agrupa hasta 50 requests por batch
4. **Flush automático**: Si la cola alcanza el máximo, se envía inmediatamente

### Flujo de ejecución

```
Request 1 → Cola
Request 2 → Cola
Request 3 → Cola
    ↓
[Espera 350ms o hasta 50 requests]
    ↓
Batch Request → [Request1, Request2, Request3] → API MEGA
    ↓
Response → [Response1, Response2, Response3]
    ↓
Futures resueltos individualmente
```

### Implementación técnica

#### 1. Estructura de datos

```python
class AsyncAPIClient:
    def __init__(self, config):
        # Cola de requests pendientes
        self._request_queue: List[Dict[str, Any]] = []
        
        # Futures para cada request (para devolver resultados)
        self._queue_futures: List[asyncio.Future] = []
        
        # Tarea de flush programada
        self._flush_task: Optional[asyncio.Task] = None
        
        # Delay antes de enviar batch (350ms como webclient)
        self._flush_delay = 0.35
        
        # Máximo de requests por batch
        self._max_batch_size = 50
```

#### 2. Método `request()`

Cuando se llama a `request()`, el request se agrega a la cola en lugar de enviarse inmediatamente:

```python
async def request(self, data: Dict[str, Any], retry_count: int = 0) -> Any:
    # Si es un retry o request inmediato, no usar batching
    immediate = data.get('_immediate', False) or retry_count > 0
    
    if immediate:
        return await self._request_immediate(data, retry_count)
    
    # Agregar a cola
    future = asyncio.Future()
    self._request_queue.append(data)
    self._queue_futures.append(future)
    
    # Programar flush si no hay uno pendiente
    if self._flush_task is None or self._flush_task.done():
        self._flush_task = asyncio.create_task(self._schedule_flush())
    
    # Si la cola está llena, flush inmediato
    if len(self._request_queue) >= self._max_batch_size:
        await self._flush_queue()
    
    return await future
```

#### 3. Programación del flush

El flush se programa con un delay de 350ms (igual que el webclient):

```python
async def _schedule_flush(self):
    """Programa un flush después del delay (350ms como webclient)."""
    await asyncio.sleep(self._flush_delay)
    await self._flush_queue()
```

#### 4. Envío del batch

Cuando se ejecuta el flush, todos los requests en cola se envían juntos:

```python
async def _flush_queue(self):
    """Envía todos los requests en cola en un solo batch."""
    # Tomar todos los requests de la cola
    queue = self._request_queue[:]
    futures = self._queue_futures[:]
    
    # Limpiar cola
    self._request_queue.clear()
    self._queue_futures.clear()
    
    # Enviar batch
    results = await self._request_batch(queue)
    
    # Resolver futures con resultados
    for i, future in enumerate(futures):
        if i < len(results):
            if isinstance(results[i], int) and results[i] < 0:
                future.set_exception(MegaAPIError(results[i], ...))
            else:
                future.set_result(results[i])
```

#### 5. Request batch

El batch se envía como un array JSON en el body:

```python
async def _request_batch(self, requests: List[Dict[str, Any]]) -> List[Any]:
    # Preparar body como array de requests
    body = json.dumps(requests)  # [request1, request2, request3, ...]
    
    # Enviar POST con el array
    async with session.post(url, data=body, headers=headers) as response:
        response_text = await response.text()
        results = self._parse_batch_response(response_text)
        return results
```

## Formato de la API

### Request individual (sin batching)

```json
POST /cs?id=123&sid=abc
Content-Type: application/json

[{"a": "ug"}]
```

### Request batch (con batching)

```json
POST /cs?id=123&sid=abc
Content-Type: application/json

[
  {"a": "ug"},
  {"a": "f", "c": 1},
  {"a": "u", "s": 1024}
]
```

### Response batch

```json
[
  {"u": "user@example.com", "c": 1},
  {"f": [...]},
  {"p": "https://upload.url/..."}
]
```

## Casos especiales

### Requests inmediatos

Algunos requests deben ejecutarse inmediatamente sin batching:

- **Retries**: Cuando se reintenta un request fallido
- **Requests con flag `_immediate`**: Requests que requieren ejecución inmediata
- **Hashcash challenges**: Cuando se necesita resolver un challenge

```python
# Request inmediato (no se agrupa)
result = await client.request({'a': 'ug', '_immediate': True})
```

### Manejo de errores en batch

Si un request en el batch falla, solo ese request falla. Los demás se procesan normalmente:

```python
# Batch con 3 requests
results = await _request_batch([
    {'a': 'ug'},      # ✅ Éxito
    {'a': 'invalid'}, # ❌ Error -2
    {'a': 'f'}        # ✅ Éxito
])

# results = [
#   {"u": "user@example.com"},
#   -2,  # Error
#   {"f": [...]}
# ]
```

### Retry de batches

Si el batch completo falla con EAGAIN, se reintenta todo el batch:

```python
# Si el batch falla con EAGAIN
if result == -3:  # EAGAIN
    delay = calculate_delay(retry_count)
    await asyncio.sleep(delay)
    return await self._request_batch(requests, retry_count + 1)
```

## Comparación con el webclient oficial

El sistema de batching en megapy replica el comportamiento del webclient oficial de MEGA:

| Característica | Webclient | megapy |
|----------------|-----------|--------|
| Delay antes de flush | 350ms | 350ms |
| Batch máximo | ~50 requests | 50 requests |
| Cola automática | Sí | Sí |
| Retry de batches | Sí | Sí |
| Flush inmediato si lleno | Sí | Sí |

### Código del webclient (referencia)

```javascript
// webclient/js/utils/api.js
async enqueue(data) {
    this.queue.add(data);
    
    if (!this.flushing) {
        // Programa flush después de 350ms
        this.flushing = new MEGADeferredController(this.flush, this).fire(350);
    }
}

async flush() {
    const queue = [...this.queue];
    this.queue.clear();
    
    // Envía todos los requests juntos
    this.rawreq = JSON.stringify(queue.map(q => q.payload));
    const res = await this.fetch(this.url, this.rawreq);
}
```

## Beneficios del batching

### 1. Reduce errores EAGAIN

- **Sin batching**: 100 requests = 100 llamadas HTTP = alta probabilidad de EAGAIN
- **Con batching**: 100 requests = 2-3 llamadas HTTP = baja probabilidad de EAGAIN

### 2. Mejor rendimiento

- Menos overhead de red (menos conexiones HTTP)
- Menos latencia total (requests agrupados)
- Mejor uso del ancho de banda

### 3. Compatibilidad con MEGA

- Replica el comportamiento del webclient oficial
- Respeta los límites de la API
- Maneja correctamente los errores de congestión

## Configuración

El batching está habilitado por defecto y no requiere configuración. Sin embargo, puedes ajustar los parámetros si es necesario:

```python
# En AsyncAPIClient.__init__()
self._flush_delay = 0.35      # Delay antes de flush (segundos)
self._max_batch_size = 50     # Máximo requests por batch
```

## Ejemplo de uso

```python
from megapy.core.api import AsyncAPIClient, APIConfig

async def example():
    config = APIConfig.default()
    async with AsyncAPIClient(config) as client:
        # Estos requests se agruparán automáticamente
        task1 = client.get_user_info()      # Request 1
        task2 = client.get_files()          # Request 2
        task3 = client.get_upload_url(1024) # Request 3
        
        # Todos se ejecutan en paralelo pero se envían en un batch
        user_info, files, upload_url = await asyncio.gather(
            task1, task2, task3
        )
        
        # Resultado: 1 llamada HTTP con 3 requests en lugar de 3 llamadas
```

## Debugging

Para ver el batching en acción, habilita el logging:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('megapy.api')
logger.setLevel(logging.DEBUG)
```

Verás mensajes como:

```
DEBUG:megapy.api:Enqueue API request: {"a": "ug"}
DEBUG:megapy.api:Enqueue API request: {"a": "f", "c": 1}
DEBUG:megapy.api:Batch request (2 requests) to https://g.api.mega.co.nz/cs?id=123
```

## Limitaciones

1. **Orden de ejecución**: Los requests en un batch se ejecutan en orden, pero los resultados pueden llegar en cualquier orden
2. **Tamaño del batch**: Máximo 50 requests por batch (configurable)
3. **Delay mínimo**: 350ms de delay antes de enviar (necesario para agrupar requests)

## Conclusión

El sistema de batching en megapy replica fielmente el comportamiento del webclient oficial de MEGA, agrupando automáticamente múltiples requests en batches para evitar errores EAGAIN y mejorar el rendimiento. Es completamente transparente para el usuario - simplemente llama a `request()` y el sistema se encarga del resto.

