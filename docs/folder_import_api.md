# API de Importación de Folders - Documentación Técnica

Esta documentación explica paso a paso cómo funciona la API para importar un folder con todos sus children, basado en el análisis del código del webclient de MEGA.

## Resumen

La importación de folders en MEGA es un proceso complejo que involucra:
1. Recopilar todos los nodos recursivamente del folder fuente
2. Preparar los nodos para la API (cifrado de keys, creación de attributes)
3. Enviar la petición API con `a: 'p'` para copiar/importar los nodos

## Arquitectura

### Clases Principales

- **`FolderImporter`** (`megapy/core/nodes/folder_importer.py`): Clase con responsabilidad única para manejar la importación de folders
- **`MegaClient.import_folder()`**: Método de alto nivel en el cliente para usar la funcionalidad

### Flujo del Proceso

```
┌─────────────────┐
│ import_folder() │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│ _collect_nodes_recursive│  ← Recopila todos los nodos recursivamente
└────────┬────────────────┘
         │
         ▼
┌──────────────────────────┐
│ _prepare_nodes_for_import│  ← Prepara nodos para API
│  ├─ Folders: nuevo key   │
│  ├─ Files: mantener key  │
│  └─ Crear attributes     │
└────────┬─────────────────┘
         │
         ▼
┌──────────────────────┐
│ _execute_import()    │  ← Llama API con a: 'p'
└──────────────────────┘
```

## Paso 1: Recopilación de Nodos

### Función: `_collect_nodes_recursive()`

**Equivalente en webclient:** `getNodesSync()` con `includeroot=True`

**Proceso:**
1. Incluye el folder raíz en la lista
2. Recorre recursivamente todos los children
3. Para cada child que es folder, repite el proceso

**Código:**
```python
def _collect_nodes_recursive(self, folder: Node) -> List[Node]:
    nodes = [folder]  # Incluir el folder raíz
    
    def collect_children(node: Node):
        for child in node.children:
            nodes.append(child)
            if child.is_folder:
                collect_children(child)  # Recursión
    
    collect_children(folder)
    return nodes
```

**Ejemplo:**
```
Folder: Documents/
  ├─ file1.txt
  ├─ Subfolder/
  │   ├─ file2.txt
  │   └─ file3.txt
  └─ file4.txt

Resultado: [Documents, file1.txt, Subfolder, file2.txt, file3.txt, file4.txt]
```

## Paso 2: Preparación de Nodos para API

### Función: `_prepare_nodes_for_import()`

**Equivalente en webclient:** `getCopyNodesSync()`

Este es el paso más complejo, donde se preparan los nodos para la API.

### 2.1 Manejo de Keys

**Folders:**
- Generan un **nuevo key aleatorio** de 16 bytes
- El key se cifra con el master key (u_k_aes) usando AES-ECB
- Se codifica en Base64 URL-safe

**Files:**
- **Mantienen su key existente**
- El key se cifra con el master key usando AES-ECB
- Se codifica en Base64 URL-safe

**Código:**
```python
if node.is_folder:
    # Folders: nuevo key aleatorio
    new_key = os.urandom(16)
    node_data['k'] = self._encrypt_key_for_api(new_key)
    key_for_attrs = new_key
else:
    # Files: mantener key existente
    if node.key:
        node_data['k'] = self._encrypt_key_for_api(node.key[:16])
        key_for_attrs = node.key[:16]
```

### 2.2 Preparación de Attributes

**Proceso:**
1. Extraer attributes existentes del nodo
2. Si `clear_attributes=True`, eliminar attributes sensibles:
   - `s4`: S4 container
   - `lbl`: Label (color)
   - `fav`: Favorite
   - `sen`: Sensitive
3. Siempre eliminar `rr`: Restore attribute
4. Cifrar attributes con el key del nodo usando AES-CBC
5. Codificar en Base64 URL-safe

**Código:**
```python
attrs = {'n': node.name}  # Name siempre requerido

# Copiar attributes existentes si están disponibles
if hasattr(node, '_raw') and node._raw:
    # Decrypt existing attributes...
    attrs.update(decrypted_attrs)

# Limpiar attributes sensibles
if clear_attributes:
    attrs.pop('s4', None)
    attrs.pop('lbl', None)
    attrs.pop('fav', None)
    attrs.pop('sen', None)

# Cifrar attributes
encrypted_attrs = AttributesPacker.pack(attrs, key_for_attrs)
node_data['a'] = Base64Encoder().encode(encrypted_attrs)
```

### 2.3 Estructura del Nodo para API

Cada nodo preparado tiene esta estructura:

```python
{
    'h': 'node_handle',      # Handle original del nodo
    't': 0 o 1,              # Tipo: 0=file, 1=folder
    'k': 'encrypted_key',    # Key cifrado con master key
    'a': 'encrypted_attrs',  # Attributes cifrados
    'p': 'parent_handle'     # Handle del parent (None para root)
}
```

**Nota sobre Parents:**
- El folder raíz tiene `p: None` (el API lo asignará al target)
- Los children mantienen su parent original
- El API automáticamente remapea los parent handles a los nuevos handles

## Paso 3: Ejecución de la API

### Función: `_execute_import()`

**Equivalente en webclient:** `copyNodes()` con llamada API `a: 'p'`

### 3.1 Request API

**Estructura del request:**
```python
{
    'a': 'p',              # Action: Put nodes (copy/import)
    'sm': 1,               # Session management
    'v': 3,                # API version
    't': 'target_handle',  # Target folder handle
    'n': [                 # Array de nodos preparados
        {
            'h': 'handle1',
            't': 1,
            'k': 'encrypted_key1',
            'a': 'encrypted_attrs1',
            'p': None
        },
        {
            'h': 'handle2',
            't': 0,
            'k': 'encrypted_key2',
            'a': 'encrypted_attrs2',
            'p': 'handle1'
        },
        # ... más nodos
    ]
}
```

### 3.2 Procesamiento del Response

**Formato del response:**
```python
{
    'result': [None, None, ...],  # None = éxito, número = error code
    'f': [...]                    # Opcional: lista actualizada de nodos
}
```

**Interpretación:**
- `result[i] = None`: El nodo `i` se importó exitosamente
- `result[i] = <número negativo>`: Error al importar el nodo `i`
- Los nuevos handles se pueden obtener del campo `f` si está presente

## Detalles de Cifrado

### Cifrado de Keys (AES-ECB)

Los keys de los nodos se cifran con el master key usando **AES-ECB mode**:

```python
def _encrypt_key_for_api(self, key: bytes) -> str:
    # Asegurar que el key sea de 16 bytes
    if len(key) < 16:
        key = key + b'\x00' * (16 - len(key))
    key = key[:16]
    
    # Cifrar con master key usando ECB
    cipher = AES.new(self._master_key[:16], AES.MODE_ECB)
    encrypted = cipher.encrypt(key)
    
    # Codificar en Base64 URL-safe
    return Base64Encoder().encode(encrypted)
```

### Cifrado de Attributes (AES-CBC)

Los attributes se cifran con el key del nodo usando **AES-CBC mode**:

```python
# Formato: MEGA{"n":"filename","e":{"i":"docid"}}
json_str = json.dumps(attrs_dict, separators=(',', ':'))
data = b'MEGA' + json_str.encode('utf-8')

# Padding a múltiplo de 16 bytes
padding_len = (16 - (len(data) % 16)) % 16
if padding_len == 0:
    padding_len = 16
data = data + (b'\x00' * padding_len)

# Cifrar con AES-CBC, IV = 16 bytes de ceros
cipher = AES.new(key[:16], AES.MODE_CBC, iv=b'\x00' * 16)
encrypted = cipher.encrypt(data)

# Codificar en Base64 URL-safe
return Base64Encoder().encode(encrypted)
```

## Uso en el Cliente

### Ejemplo Básico

```python
from megapy import MegaClient

async def main():
    async with MegaClient("session") as mega:
        # Encontrar folder fuente
        source = await mega.find("Documents")
        
        # Encontrar folder destino
        target = await mega.find("Backups")
        
        # Importar folder con todos sus children
        imported = await mega.import_folder(
            source_folder=source,
            target_folder=target,
            clear_attributes=True  # Limpiar attributes sensibles
        )
        
        print(f"Importados {len(imported)} nodos")

asyncio.run(main())
```

### Ejemplo Avanzado

```python
# Importar desde un folder link (public folder)
async def import_public_folder():
    async with MegaClient("session") as mega:
        # Obtener folder público (desde link)
        public_folder = await mega.get_public_folder("folder_link")
        
        # Importar a mi cuenta
        target = await mega.get_root()
        imported = await mega.import_folder(
            source_folder=public_folder,
            target_folder=target,
            clear_attributes=True
        )
        
        return imported
```

## Consideraciones Importantes

### 1. Límites de Tamaño

- El API tiene límites en el número de nodos por request
- Para folders muy grandes (>6000 nodos), considerar dividir en múltiples requests

### 2. Manejo de Errores

- Verificar el response para errores individuales
- Algunos nodos pueden fallar mientras otros tienen éxito
- Reintentar nodos fallidos si es necesario

### 3. Actualización del Tree

- Después de importar, recargar los nodos con `_load_nodes()`
- Los nuevos handles estarán disponibles en el tree

### 4. Attributes Sensibles

- Por defecto, `clear_attributes=True` elimina:
  - Labels de color
  - Favorites
  - S4 containers
  - Sensitive flags
- Esto es importante para imports desde folder links públicos

### 5. Parent Relationships

- El API maneja automáticamente el remapeo de parent handles
- No es necesario calcular manualmente los nuevos handles de parents
- El folder raíz se asigna automáticamente al target

## Referencias del Webclient

### Funciones Equivalentes

| megapy | webclient | Descripción |
|--------|-----------|-------------|
| `_collect_nodes_recursive()` | `getNodesSync()` | Recopilar nodos recursivamente |
| `_prepare_nodes_for_import()` | `getCopyNodesSync()` | Preparar nodos para API |
| `_execute_import()` | `copyNodes()` | Ejecutar API call |
| `import_folder()` | `importFolderLinkNodes()` | Función principal |

### Archivos del Webclient

- `webclient/js/fm/megadata/nodes.js`:
  - `getCopyNodes()` (línea 2806)
  - `getCopyNodesSync()` (línea 2842)
  - `copyNodes()` (línea 937)
  - `importFolderLinkNodes()` (línea 4921)

- `webclient/js/fm/link-import.js`:
  - Lógica de importación desde folder links (línea 695)

## Testing

Para probar la funcionalidad:

```python
# Test básico
async def test_import():
    async with MegaClient("test_session") as mega:
        # Crear folder de prueba
        test_folder = await mega.create_folder("TestImport")
        
        # Crear algunos archivos/folders dentro
        # ...
        
        # Importar a otro location
        target = await mega.get_root()
        imported = await mega.import_folder(test_folder, target)
        
        assert len(imported) > 0
        print("✓ Import successful")
```

## Conclusión

La importación de folders es un proceso complejo que requiere:
1. Recopilación recursiva de nodos
2. Preparación cuidadosa de keys y attributes
3. Cifrado correcto con los algoritmos apropiados
4. Manejo adecuado de parent relationships

La clase `FolderImporter` encapsula toda esta lógica con responsabilidad única, haciendo el proceso más mantenible y testeable.

