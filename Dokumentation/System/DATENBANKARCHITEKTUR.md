# Datenbankarchitektur für das AIMA-System

Dieses Dokument beschreibt die Datenbankarchitektur des AIMA-Systems, einschließlich der Auswahl der Datenbanktypen, Schemata, Indizierungsstrategien und Optimierungen für die effiziente Verarbeitung und Abfrage großer Mengen multimodaler Daten.

## 1. Übersicht der Datenbankarchitektur

### 1.1 Mehrschichtige Datenbankstrategie

Das AIMA-System verwendet eine mehrschichtige Datenbankstrategie, die verschiedene Datenbanktypen für unterschiedliche Anforderungen kombiniert:

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Anwendungsschicht                               │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────────┐
│                     Datenabstraktionsschicht                        │
│  (Einheitliche API, Caching, Konsistenzprüfung)                    │
└─────────┬─────────────────────┬──────────────────────┬──────────────┘
          │                     │                      │
┌─────────▼─────────┐  ┌────────▼────────┐  ┌─────────▼─────────────┐
│  Dokumenten-DB    │  │  Vektordatenbank │  │  Objektspeicher       │
│  (MongoDB)        │  │  (Milvus/FAISS)  │  │  (MinIO/S3)           │
│                   │  │                  │  │                        │
│  - Metadaten      │  │  - Einbettungen  │  │  - Mediendateien      │
│  - Analyseergebnisse│  │  - Ähnlichkeits- │  │  - Große Binärdaten   │
│  - Dossiers       │  │    suche         │  │  - Checkpoints        │
└─────────┬─────────┘  └────────┬────────┘  └─────────┬─────────────┘
          │                     │                      │
┌─────────▼─────────────────────▼──────────────────────▼─────────────┐
│                     Datenspeicherschicht                            │
│  (Persistenz, Backup, Replikation)                                 │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Datenbanktypen und ihre Verwendung

#### Dokumentendatenbank (MongoDB)

**Primäre Verwendung:**
- Speicherung strukturierter und semi-strukturierter Metadaten
- Analyseergebnisse aus verschiedenen ML-Modellen
- Dossiers und zusammengeführte Informationen
- Konfigurationen und Systemeinstellungen

**Vorteile für AIMA:**
- Flexible Schemata für unterschiedliche Metadatentypen
- Gute Leistung für Lese- und Schreiboperationen
- Unterstützung für komplexe Abfragen und Aggregationen
- Horizontale Skalierbarkeit durch Sharding

#### Vektordatenbank (Milvus/FAISS)

**Primäre Verwendung:**
- Speicherung von Einbettungsvektoren aus ML-Modellen
- Ähnlichkeitssuche für Gesichter, Objekte, Audiomerkmale
- Multimodale Abfragen über verschiedene Medientypen hinweg

**Vorteile für AIMA:**
- Optimiert für hochdimensionale Vektoroperationen
- Effiziente Ähnlichkeitssuche (k-NN, ANN)
- Skalierbarkeit für Millionen von Vektoren
- Integration mit ML-Frameworks

#### Objektspeicher (MinIO/S3-kompatibel)

**Primäre Verwendung:**
- Speicherung von Originalmediendateien (Video, Audio, Bilder)
- Zwischenergebnisse und verarbeitete Mediendateien
- Modell-Checkpoints und große Binärdaten
- Langzeitarchivierung

**Vorteile für AIMA:**
- Kostengünstige Speicherung großer Datenmengen
- Hohe Durchsatzraten für Medienstreaming
- Versionierung und Lebenszyklusmanagement
- Kompatibilität mit Cloud-Speicherdiensten

## 2. Datenbankschema und Datenmodellierung

### 2.1 Dokumentendatenbank-Schema

#### Sammlungen (Collections)

**media_items**
```json
{
  "_id": "ObjectId",
  "media_id": "string",  // Eindeutige ID für das Medienitem
  "type": "string",      // video, audio, image
  "filename": "string",
  "upload_timestamp": "date",
  "duration_seconds": "number",  // für Video/Audio
  "resolution": "string",       // für Video/Bild
  "file_size_bytes": "number",
  "mime_type": "string",
  "hash": "string",            // für Deduplizierung
  "storage_location": {
    "type": "string",          // s3, minio, local
    "bucket": "string",
    "path": "string"
  },
  "processing_status": "string",  // pending, processing, completed, failed
  "analysis_jobs": [{
    "job_id": "string",
    "type": "string",
    "status": "string",
    "created_at": "date",
    "completed_at": "date"
  }]
}
```

**analysis_results**
```json
{
  "_id": "ObjectId",
  "result_id": "string",
  "media_id": "string",
  "job_id": "string",
  "analysis_type": "string",  // face_detection, speech_recognition, etc.
  "model_info": {
    "name": "string",
    "version": "string"
  },
  "timestamp": "date",
  "time_range": {           // für zeitbasierte Medien
    "start_seconds": "number",
    "end_seconds": "number"
  },
  "spatial_location": {     // für räumliche Daten in Bildern/Videos
    "x": "number",
    "y": "number",
    "width": "number",
    "height": "number"
  },
  "confidence": "number",
  "metadata": "object",     // Modellspezifische Metadaten
  "vector_embeddings": {    // Referenzen zu Vektordatenbank
    "embedding_id": "string",
    "dimensions": "number",
    "model": "string"
  }
}
```

**persons**
```json
{
  "_id": "ObjectId",
  "person_id": "string",
  "temporary": "boolean",   // Temporäre oder bestätigte Person
  "created_at": "date",
  "last_updated": "date",
  "confidence": "number",
  "appearances": [{
    "media_id": "string",
    "result_ids": ["string"],  // IDs der Analyseergebnisse
    "time_ranges": [{
      "start_seconds": "number",
      "end_seconds": "number"
    }],
    "confidence": "number"
  }],
  "face_embeddings": [{
    "embedding_id": "string",
    "confidence": "number",
    "source_result_id": "string"
  }],
  "voice_embeddings": [{
    "embedding_id": "string",
    "confidence": "number",
    "source_result_id": "string"
  }],
  "attributes": {          // Zusammengeführte Attribute
    "estimated_age": "number",
    "gender": "string",
    "clothing": ["string"],
    "distinguishing_features": ["string"]
  }
}
```

**dossiers**
```json
{
  "_id": "ObjectId",
  "dossier_id": "string",
  "title": "string",
  "created_at": "date",
  "last_updated": "date",
  "status": "string",      // draft, published, archived
  "media_items": ["string"],  // IDs der enthaltenen Medien
  "persons": [{
    "person_id": "string",
    "relevance_score": "number",
    "appearances": [{
      "media_id": "string",
      "time_ranges": [{
        "start_seconds": "number",
        "end_seconds": "number"
      }]
    }]
  }],
  "events": [{
    "event_id": "string",
    "description": "string",
    "confidence": "number",
    "media_references": [{
      "media_id": "string",
      "time_range": {
        "start_seconds": "number",
        "end_seconds": "number"
      }
    }]
  }],
  "summary": "string",     // LLM-generierte Zusammenfassung
  "tags": ["string"],
  "metadata": "object"     // Zusätzliche Metadaten
}
```

### 2.2 Vektordatenbank-Schema

#### Sammlungen (Collections)

**face_embeddings**
- Dimensionen: 512 (je nach Modell)
- Metadaten: person_id, media_id, confidence, timestamp
- Index-Typ: HNSW (Hierarchical Navigable Small World)

**voice_embeddings**
- Dimensionen: 256 (je nach Modell)
- Metadaten: person_id, media_id, confidence, timestamp
- Index-Typ: HNSW

**object_embeddings**
- Dimensionen: 1024 (je nach Modell)
- Metadaten: object_class, media_id, confidence, timestamp
- Index-Typ: HNSW

**scene_embeddings**
- Dimensionen: 2048 (je nach Modell)
- Metadaten: scene_description, media_id, timestamp
- Index-Typ: HNSW

### 2.3 Objektspeicher-Organisation

#### Bucket-Struktur

**media-originals**
- Originale Mediendateien, unveränderter Zustand
- Organisiert nach: `/{year}/{month}/{day}/{media_id}.{extension}`

**media-processed**
- Verarbeitete Mediendateien (z.B. transkodierte Videos, normalisierte Bilder)
- Organisiert nach: `/{media_id}/{variant}/{filename}`

**analysis-artifacts**
- Zwischenergebnisse und Artefakte aus der Analyse
- Organisiert nach: `/{media_id}/{job_id}/{artifact_type}/{filename}`

**model-checkpoints**
- Checkpoints für unterbrochene Analysen
- Organisiert nach: `/{job_id}/{timestamp}/{checkpoint_name}`

**exports**
- Exportierte Dossiers und Berichte
- Organisiert nach: `/{dossier_id}/{export_timestamp}/{format}/{filename}`

## 3. Indizierungsstrategien

### 3.1 Dokumentendatenbank-Indizes

#### Primäre Indizes

```javascript
// media_items Collection
db.media_items.createIndex({ "media_id": 1 }, { unique: true });
db.media_items.createIndex({ "hash": 1 });
db.media_items.createIndex({ "processing_status": 1 });
db.media_items.createIndex({ "upload_timestamp": -1 });
db.media_items.createIndex({ "type": 1, "upload_timestamp": -1 });

// analysis_results Collection
db.analysis_results.createIndex({ "result_id": 1 }, { unique: true });
db.analysis_results.createIndex({ "media_id": 1 });
db.analysis_results.createIndex({ "job_id": 1 });
db.analysis_results.createIndex({ "analysis_type": 1 });
db.analysis_results.createIndex({ "media_id": 1, "analysis_type": 1 });
db.analysis_results.createIndex({ "time_range.start_seconds": 1, "time_range.end_seconds": 1 });

// persons Collection
db.persons.createIndex({ "person_id": 1 }, { unique: true });
db.persons.createIndex({ "temporary": 1 });
db.persons.createIndex({ "appearances.media_id": 1 });
db.persons.createIndex({ "face_embeddings.embedding_id": 1 });
db.persons.createIndex({ "voice_embeddings.embedding_id": 1 });

// dossiers Collection
db.dossiers.createIndex({ "dossier_id": 1 }, { unique: true });
db.dossiers.createIndex({ "status": 1, "last_updated": -1 });
db.dossiers.createIndex({ "media_items": 1 });
db.dossiers.createIndex({ "persons.person_id": 1 });
db.dossiers.createIndex({ "tags": 1 });
```

#### Zusammengesetzte Indizes für häufige Abfragen

```javascript
// Für Abfragen nach Medientyp und Verarbeitungsstatus
db.media_items.createIndex({ "type": 1, "processing_status": 1 });

// Für Abfragen nach Analyseergebnissen in einem Zeitbereich
db.analysis_results.createIndex({ 
  "media_id": 1, 
  "analysis_type": 1, 
  "time_range.start_seconds": 1 
});

// Für Personensuche nach Attributen
db.persons.createIndex({ 
  "attributes.estimated_age": 1,
  "attributes.gender": 1
});

// Für Dossiersuche nach Status und Personen
db.dossiers.createIndex({ 
  "status": 1, 
  "persons.person_id": 1 
});
```

### 3.2 Vektordatenbank-Indizes

#### HNSW-Indexkonfiguration

```python
# Beispielkonfiguration für Milvus
face_collection_params = {
    "fields": [
        {"name": "embedding_id", "type": DataType.VARCHAR, "is_primary": True, "max_length": 100},
        {"name": "embedding", "type": DataType.FLOAT_VECTOR, "dim": 512},
        {"name": "person_id", "type": DataType.VARCHAR, "max_length": 100},
        {"name": "media_id", "type": DataType.VARCHAR, "max_length": 100},
        {"name": "confidence", "type": DataType.FLOAT},
        {"name": "timestamp", "type": DataType.INT64}
    ],
    "index_params": {
        "index_type": "HNSW",
        "metric_type": "COSINE",
        "params": {"M": 16, "efConstruction": 200}
    },
    "search_params": {
        "metric_type": "COSINE",
        "params": {"ef": 100}
    }
}
```

## 4. Datenbankoptimierungen

### 4.1 Leistungsoptimierungen

#### Caching-Strategien

- **Anwendungsseitiges Caching**:
  - Redis für häufig abgefragte Metadaten und Analyseergebnisse
  - Mehrschichtiges Caching (Memory, SSD, Netzwerk)
  - Time-to-Live (TTL) basierend auf Zugriffsmustern

- **Datenbankinternes Caching**:
  - Optimierte WiredTiger-Cache-Konfiguration für MongoDB
  - Speicherreservierung für Vektordatenbank-Indizes
  - Vorgeladen häufig verwendete Indizes

#### Abfrageoptimierungen

- **Aggregation Pipeline Optimierung**:
  - Verwendung von `$match` früh in der Pipeline
  - Projektion unnötiger Felder mit `$project`
  - Verwendung von `$limit` und `$skip` für Paginierung

- **Vektorabfrageoptimierung**:
  - Vorfilterung mit Metadaten vor Vektorsuche
  - Anpassung der Suchparameter basierend auf Genauigkeits-/Geschwindigkeitsanforderungen
  - Batch-Verarbeitung für große Abfragen

### 4.2 Skalierungsstrategien

#### Horizontale Skalierung

- **MongoDB-Sharding**:
  - Shard-Schlüssel: `{ media_id: "hashed" }` für gleichmäßige Verteilung
  - Zonenbasiertes Sharding für geografische Optimierung

- **Vektordatenbank-Partitionierung**:
  - Partitionierung nach Medientyp und Zeitraum
  - Replikation für Lesezugriff-Skalierung

- **Objektspeicher-Skalierung**:
  - Multi-Cluster-Konfiguration
  - Automatische Erweiterung des Speicherplatzes

#### Vertikale Skalierung

- **Ressourcenoptimierung**:
  - SSD/NVMe-Speicher für Datenbankindizes
  - Optimierte RAM-Zuweisung basierend auf Workload
  - CPU-Optimierung für Abfrageverarbeitung

### 4.3 Datenlebenszyklus-Management

#### Datenarchivierung

- **Automatisierte Archivierungsrichtlinien**:
  - Verschiebung selten verwendeter Daten in kostengünstigeren Speicher
  - Komprimierung älterer Analyseergebnisse
  - Beibehaltung von Zusammenfassungen und Schlüsselmetadaten

- **Wiederherstellungsmechanismen**:
  - On-Demand-Wiederherstellung archivierter Daten
  - Priorisierte Wiederherstellung basierend auf Benutzeranforderungen

## 5. Implementierungsdetails

### 5.1 Datenbankabstraktionsschicht

```python
class DatabaseManager:
    def __init__(self, config):
        self.config = config
        self.document_db = self._init_document_db()
        self.vector_db = self._init_vector_db()
        self.object_storage = self._init_object_storage()
        self.cache = self._init_cache()
    
    def _init_document_db(self):
        """Initialisiert die Dokumentendatenbank-Verbindung"""
        client = pymongo.MongoClient(
            self.config['document_db']['connection_string'],
            **self.config['document_db']['options']
        )
        return client[self.config['document_db']['database_name']]
    
    def _init_vector_db(self):
        """Initialisiert die Vektordatenbank-Verbindung"""
        if self.config['vector_db']['type'] == 'milvus':
            from pymilvus import connections, Collection
            connections.connect(
                alias="default", 
                host=self.config['vector_db']['host'],
                port=self.config['vector_db']['port']
            )
            return {
                'face_embeddings': Collection("face_embeddings"),
                'voice_embeddings': Collection("voice_embeddings"),
                'object_embeddings': Collection("object_embeddings"),
                'scene_embeddings': Collection("scene_embeddings")
            }
        else:
            # Implementierung für andere Vektordatenbanken
            pass
    
    def _init_object_storage(self):
        """Initialisiert die Objektspeicher-Verbindung"""
        if self.config['object_storage']['type'] == 'minio':
            from minio import Minio
            client = Minio(
                self.config['object_storage']['endpoint'],
                access_key=self.config['object_storage']['access_key'],
                secret_key=self.config['object_storage']['secret_key'],
                secure=self.config['object_storage']['secure']
            )
            return client
        elif self.config['object_storage']['type'] == 's3':
            import boto3
            return boto3.client('s3', **self.config['object_storage']['options'])
    
    def _init_cache(self):
        """Initialisiert den Cache"""
        import redis
        return redis.Redis(
            host=self.config['cache']['host'],
            port=self.config['cache']['port'],
            db=self.config['cache']['db']
        )
    
    def store_media_item(self, media_item):
        """Speichert ein neues Medienitem in der Dokumentendatenbank"""
        # Generiere eindeutige ID, falls nicht vorhanden
        if 'media_id' not in media_item:
            media_item['media_id'] = str(uuid.uuid4())
        
        # Setze Standardwerte
        media_item.setdefault('upload_timestamp', datetime.now())
        media_item.setdefault('processing_status', 'pending')
        
        # Speichere in Dokumentendatenbank
        result = self.document_db.media_items.insert_one(media_item)
        
        # Aktualisiere Cache
        cache_key = f"media:{media_item['media_id']}"
        self.cache.set(cache_key, json.dumps(media_item), ex=3600)  # 1 Stunde TTL
        
        return media_item['media_id']
    
    def store_analysis_result(self, result, vector_embedding=None):
        """Speichert ein Analyseergebnis und optional einen Einbettungsvektor"""
        # Generiere eindeutige ID, falls nicht vorhanden
        if 'result_id' not in result:
            result['result_id'] = str(uuid.uuid4())
        
        # Wenn ein Einbettungsvektor vorhanden ist, speichere ihn in der Vektordatenbank
        if vector_embedding is not None:
            embedding_id = self._store_vector_embedding(
                result['analysis_type'], 
                vector_embedding, 
                {
                    'result_id': result['result_id'],
                    'media_id': result['media_id'],
                    'confidence': result.get('confidence', 1.0)
                }
            )
            
            # Füge Referenz zum Einbettungsvektor hinzu
            result['vector_embeddings'] = {
                'embedding_id': embedding_id,
                'dimensions': len(vector_embedding),
                'model': result.get('model_info', {}).get('name', 'unknown')
            }
        
        # Speichere in Dokumentendatenbank
        self.document_db.analysis_results.insert_one(result)
        
        # Aktualisiere Cache
        cache_key = f"result:{result['result_id']}"
        self.cache.set(cache_key, json.dumps(result), ex=3600)  # 1 Stunde TTL
        
        return result['result_id']
    
    def _store_vector_embedding(self, embedding_type, vector, metadata):
        """Speichert einen Einbettungsvektor in der Vektordatenbank"""
        embedding_id = str(uuid.uuid4())
        
        # Wähle die richtige Sammlung basierend auf dem Einbettungstyp
        collection_map = {
            'face_detection': 'face_embeddings',
            'speaker_diarization': 'voice_embeddings',
            'object_detection': 'object_embeddings',
            'scene_analysis': 'scene_embeddings'
        }
        
        collection_name = collection_map.get(embedding_type, 'general_embeddings')
        
        if collection_name in self.vector_db:
            collection = self.vector_db[collection_name]
            
            # Bereite Daten für Einfügung vor
            insert_data = {
                'embedding_id': embedding_id,
                'embedding': vector,
                'timestamp': int(time.time())
            }
            
            # Füge Metadaten hinzu
            insert_data.update(metadata)
            
            # Füge in Vektordatenbank ein
            collection.insert([insert_data])
        
        return embedding_id
    
    def find_similar_vectors(self, embedding_type, query_vector, limit=10, metadata_filters=None):
        """Findet ähnliche Vektoren in der Vektordatenbank"""
        collection_map = {
            'face': 'face_embeddings',
            'voice': 'voice_embeddings',
            'object': 'object_embeddings',
            'scene': 'scene_embeddings'
        }
        
        collection_name = collection_map.get(embedding_type, 'general_embeddings')
        
        if collection_name in self.vector_db:
            collection = self.vector_db[collection_name]
            
            # Erstelle Abfrage mit optionalen Metadatenfiltern
            search_params = {"metric_type": "COSINE", "params": {"ef": 100}}
            expr = None
            
            if metadata_filters:
                # Erstelle Filterausdruck basierend auf Metadaten
                conditions = []
                for key, value in metadata_filters.items():
                    if isinstance(value, list):
                        conditions.append(f"{key} in {value}")
                    else:
                        conditions.append(f"{key} == '{value}'")
                
                if conditions:
                    expr = " and ".join(conditions)
            
            # Führe Vektorsuche durch
            results = collection.search(
                data=[query_vector],
                anns_field="embedding",
                param=search_params,
                limit=limit,
                expr=expr,
                output_fields=["embedding_id", "confidence", "media_id", "result_id"]
            )
            
            return results[0]  # Ergebnisse für den ersten (und einzigen) Abfragevektor
        
        return []
    
    def store_object(self, bucket, object_path, data, metadata=None):
        """Speichert ein Objekt im Objektspeicher"""
        try:
            # Stelle sicher, dass der Bucket existiert
            if not self.object_storage.bucket_exists(bucket):
                self.object_storage.make_bucket(bucket)
            
            # Bereite Metadaten vor, falls vorhanden
            object_metadata = {}
            if metadata:
                # Konvertiere Metadaten in das richtige Format
                for key, value in metadata.items():
                    object_metadata[key] = str(value)
            
            # Bestimme Content-Type basierend auf Dateiendung
            content_type = mimetypes.guess_type(object_path)[0] or 'application/octet-stream'
            
            # Speichere Objekt
            if isinstance(data, (str, bytes)):
                # Direktes Hochladen von Daten
                if isinstance(data, str):
                    data = data.encode('utf-8')
                
                data_stream = io.BytesIO(data)
                data_size = len(data)
                
                self.object_storage.put_object(
                    bucket_name=bucket,
                    object_name=object_path,
                    data=data_stream,
                    length=data_size,
                    content_type=content_type,
                    metadata=object_metadata
                )
            else:
                # Hochladen aus Datei oder Stream
                self.object_storage.fput_object(
                    bucket_name=bucket,
                    object_name=object_path,
                    file_path=data,
                    content_type=content_type,
                    metadata=object_metadata
                )
            
            return {
                'bucket': bucket,
                'path': object_path,
                'size': data_size if 'data_size' in locals() else None,
                'content_type': content_type
            }
            
        except Exception as e:
            logging.error(f"Error storing object in {bucket}/{object_path}: {str(e)}")
            raise
    
    def get_object(self, bucket, object_path, download_path=None):
        """Holt ein Objekt aus dem Objektspeicher"""
        try:
            if download_path:
                # Herunterladen in eine Datei
                self.object_storage.fget_object(
                    bucket_name=bucket,
                    object_name=object_path,
                    file_path=download_path
                )
                return download_path
            else:
                # Herunterladen in den Speicher
                response = self.object_storage.get_object(
                    bucket_name=bucket,
                    object_name=object_path
                )
                
                # Lese Daten
                data = response.read()
                response.close()
                response.release_conn()
                
                return data
                
        except Exception as e:
            logging.error(f"Error retrieving object from {bucket}/{object_path}: {str(e)}")
            raise
```

### 5.2 Transaktionsmanagement

```python
class DatabaseTransaction:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.document_db = db_manager.document_db
        self.operations = []
        self.rollback_operations = []
    
    def add_operation(self, operation_type, collection, document, rollback_info=None):
        """Fügt eine Operation zur Transaktion hinzu"""
        self.operations.append({
            'type': operation_type,  # 'insert', 'update', 'delete'
            'collection': collection,
            'document': document
        })
        
        if rollback_info:
            self.rollback_operations.append(rollback_info)
    
    def execute(self):
        """Führt die Transaktion aus"""
        # MongoDB-Sitzung für Transaktion starten
        with self.document_db.client.start_session() as session:
            try:
                # Transaktion starten
                with session.start_transaction():
                    for op in self.operations:
                        collection = self.document_db[op['collection']]
                        
                        if op['type'] == 'insert':
                            collection.insert_one(op['document'], session=session)
                        elif op['type'] == 'update':
                            collection.update_one(
                                op['filter'], 
                                {'$set': op['document']}, 
                                session=session
                            )
                        elif op['type'] == 'delete':
                            collection.delete_one(op['filter'], session=session)
                
                # Wenn wir hier ankommen, wurde die Transaktion erfolgreich festgeschrieben
                return True
                
            except Exception as e:
                logging.error(f"Transaction failed: {str(e)}")
                # Transaktion wird automatisch abgebrochen
                self._manual_rollback()
                return False
    
    def _manual_rollback(self):
        """Führt manuelle Rollback-Operationen für nicht-transaktionale Datenbanken durch"""
        # Rollback für Vektordatenbank und Objektspeicher
        for rollback_op in reversed(self.rollback_operations):
            try:
                if rollback_op['type'] == 'vector_delete':
                    # Lösche Vektoren, die während der Transaktion eingefügt wurden
                    collection = self.db_manager.vector_db[rollback_op['collection']]
                    collection.delete(rollback_op['ids'])
                    
                elif rollback_op['type'] == 'object_delete':
                    # Lösche Objekte, die während der Transaktion hochgeladen wurden
                    self.db_manager.object_storage.remove_object(
                        bucket_name=rollback_op['bucket'],
                        object_name=rollback_op['path']
                    )
            except Exception as e:
                logging.error(f"Rollback operation failed: {str(e)}")
```

## 6. Datenmigration und Versionierung

### 6.1 Migrationsstrategie

```python
class DatabaseMigration:
    def __init__(self, db_manager, migration_config):
        self.db_manager = db_manager
        self.migration_config = migration_config
        self.migrations_collection = db_manager.document_db['system_migrations']
    
    def get_current_version(self):
        """Holt die aktuelle Datenbankversion"""
        version_doc = self.migrations_collection.find_one(
            {"_id": "current_version"}
        )
        
        if version_doc:
            return version_doc["version"]
        else:
            # Keine Version gefunden, initialisiere mit 0
            self.migrations_collection.insert_one({
                "_id": "current_version",
                "version": 0,
                "updated_at": datetime.now()
            })
            return 0
    
    def run_pending_migrations(self):
        """Führt ausstehende Migrationen aus"""
        current_version = self.get_current_version()
        target_version = self.migration_config["target_version"]
        
        if current_version >= target_version:
            logging.info(f"Database already at version {current_version}, no migrations needed")
            return True
        
        # Hole alle ausstehenden Migrationen
        pending_migrations = [m for m in self.migration_config["migrations"]
                             if m["version"] > current_version and m["version"] <= target_version]
        
        # Sortiere nach Version
        pending_migrations.sort(key=lambda x: x["version"])
        
        for migration in pending_migrations:
            logging.info(f"Running migration to version {migration['version']}: {migration['description']}")
            
            try:
                # Führe Migration aus
                if migration["type"] == "mongodb":
                    self._run_mongodb_migration(migration)
                elif migration["type"] == "vector_db":
                    self._run_vector_db_migration(migration)
                elif migration["type"] == "object_storage":
                    self._run_object_storage_migration(migration)
                
                # Aktualisiere Version
                self.migrations_collection.update_one(
                    {"_id": "current_version"},
                    {"$set": {
                        "version": migration["version"],
                        "updated_at": datetime.now()
                    }}
                )
                
                # Protokolliere erfolgreiche Migration
                self.migrations_collection.insert_one({
                    "version": migration["version"],
                    "description": migration["description"],
                    "executed_at": datetime.now(),
                    "success": True
                })
                
                logging.info(f"Migration to version {migration['version']} completed successfully")
                
            except Exception as e:
                error_msg = f"Migration to version {migration['version']} failed: {str(e)}"
                logging.error(error_msg)
                
                # Protokolliere fehlgeschlagene Migration
                self.migrations_collection.insert_one({
                    "version": migration["version"],
                    "description": migration["description"],
                    "executed_at": datetime.now(),
                    "success": False,
                    "error": error_msg
                })
                
                return False
        
        return True
    
    def _run_mongodb_migration(self, migration):
        """Führt eine MongoDB-Migration aus"""
        db = self.db_manager.document_db
        
        for operation in migration["operations"]:
            if operation["action"] == "create_collection":
                if operation["collection"] not in db.list_collection_names():
                    db.create_collection(operation["collection"])
            
            elif operation["action"] == "create_index":
                collection = db[operation["collection"]]
                index_spec = operation["index_spec"]
                index_options = operation.get("index_options", {})
                collection.create_index(index_spec, **index_options)
            
            elif operation["action"] == "drop_index":
                collection = db[operation["collection"]]
                index_name = operation["index_name"]
                collection.drop_index(index_name)
            
            elif operation["action"] == "update_documents":
                collection = db[operation["collection"]]
                filter_spec = operation["filter"]
                update_spec = operation["update"]
                multi = operation.get("multi", False)
                
                if multi:
                    collection.update_many(filter_spec, update_spec)
                else:
                    collection.update_one(filter_spec, update_spec)
            
            elif operation["action"] == "rename_field":
                collection = db[operation["collection"]]
                old_field = operation["old_field"]
                new_field = operation["new_field"]
                
                collection.update_many(
                    {old_field: {"$exists": True}},
                    {"$rename": {old_field: new_field}}
                )
    
    def _run_vector_db_migration(self, migration):
        """Führt eine Vektordatenbank-Migration aus"""
        # Implementierung für Vektordatenbank-Migrationen
        pass
    
    def _run_object_storage_migration(self, migration):
        """Führt eine Objektspeicher-Migration aus"""
        # Implementierung für Objektspeicher-Migrationen
        pass
```

## 7. Sicherheit und Datenschutz

### 7.1 Zugriffskontrollen

- **Rollenbasierte Zugriffskontrollen (RBAC)**:
  - Detaillierte Berechtigungen für verschiedene Benutzerrollen
  - Granulare Kontrolle auf Sammlungs- und Dokumentebene
  - Audit-Logging für alle Datenbankzugriffe

- **Netzwerksicherheit**:
  - Verschlüsselte Verbindungen (TLS/SSL)
  - IP-basierte Zugriffsbeschränkungen
  - VPC/Subnetz-Isolation für Datenbankdienste

### 7.2 Datenverschlüsselung

- **Verschlüsselung im Ruhezustand**:
  - Transparente Datenverschlüsselung für MongoDB
  - Serverseitige Verschlüsselung für Objektspeicher
  - Verschlüsselte Backups

- **Verschlüsselung bei der Übertragung**:
  - TLS für alle Datenbankverbindungen
  - Sichere API-Endpunkte
  - VPN für standortübergreifende Kommunikation

### 7.3 Datenschutzmaßnahmen

- **Pseudonymisierung**:
  - Trennung von identifizierenden Informationen
  - Verwendung von UUIDs statt natürlicher Schlüssel

- **Datenzugriffsprotokolle**:
  - Detaillierte Protokollierung aller Datenzugriffe
  - Automatische Erkennung verdächtiger Zugriffsmuster

- **Datenaufbewahrungsrichtlinien**:
  - Automatisierte Löschung nach definierten Zeiträumen
  - Selektive Archivierung basierend auf Datenklassifizierung

## 8. Überwachung und Wartung

### 8.1 Leistungsüberwachung

- **Metriken**:
  - Abfrageausführungszeiten
  - Index-Nutzung und -Effizienz
  - Cache-Trefferquoten
  - Speichernutzung und -wachstum

- **Alarme**:
  - Schwellenwertbasierte Alarme für kritische Metriken
  - Anomalieerkennung für ungewöhnliche Muster
  - Eskalationspfade für verschiedene Alarmtypen

### 8.2 Backup- und Wiederherstellungsstrategien

- **Backup-Zeitplan**:
  - Tägliche vollständige Backups
  - Stündliche inkrementelle Backups
  - Point-in-Time-Recovery für kritische Daten

- **Wiederherstellungstests**:
  - Regelmäßige Wiederherstellungstests
  - Dokumentierte Wiederherstellungsverfahren
  - Automatisierte Wiederherstellungsskripte

### 8.3 Wartungsprozeduren

- **Geplante Wartung**:
  - Indexneuerstellung und -optimierung
  - Datenbankstatistikaktualisierung
  - Versionsupdates und Patches

- **Automatisierte Wartung**:
  - Skripte für routinemäßige Wartungsaufgaben
  - Überwachung der Wartungsergebnisse
  - Rollback-Mechanismen für fehlgeschlagene Wartung