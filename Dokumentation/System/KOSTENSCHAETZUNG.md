# Kostenschätzung für AIMA

Dieses Dokument spezifiziert den Mechanismus zur Kostenschätzung im AIMA-System, der Benutzern vor der Ausführung von Analysen eine Prognose der zu erwartenden Kosten liefert.

## 1. Übersicht

Die Kostenschätzung ist ein wesentlicher Bestandteil des AIMA-Systems, der Transparenz und Kostenkontrolle für Benutzer ermöglicht. Durch präzise Vorhersagen der zu erwartenden Kosten vor der Ausführung von Analysen können Benutzer informierte Entscheidungen treffen und ihr Budget effektiv verwalten.

## 2. Anforderungen

### 2.1 Funktionale Anforderungen

- **Präzise Schätzungen**: Genaue Vorhersage der Kosten basierend auf Eingabedaten und Analyseparametern
- **Transparenz**: Detaillierte Aufschlüsselung der geschätzten Kosten nach Komponenten
- **Echtzeit-Berechnung**: Sofortige Aktualisierung der Kostenschätzung bei Änderung von Parametern
- **Historische Vergleiche**: Vergleich mit ähnlichen früheren Analysen zur Verbesserung der Genauigkeit
- **Kostenoptimierungsvorschläge**: Empfehlungen zur Reduzierung der Kosten

### 2.2 Nicht-funktionale Anforderungen

- **Genauigkeit**: Maximale Abweichung von 15% zwischen geschätzten und tatsächlichen Kosten
- **Leistung**: Berechnung der Kostenschätzung in unter 2 Sekunden
- **Skalierbarkeit**: Unterstützung von komplexen Analysen mit mehreren Modulen und großen Datenmengen
- **Anpassbarkeit**: Einfache Aktualisierung der Kostenmodelle bei Änderungen der Ressourcenpreise

## 3. Kostenmodell

### 3.1 Kostenfaktoren

Das Kostenmodell berücksichtigt folgende Faktoren:

#### 3.1.1 Rechenressourcen

- **GPU-Nutzung**: Kosten pro GPU-Stunde, abhängig vom GPU-Typ (z.B. NVIDIA T4, V100, A100)
- **CPU-Nutzung**: Kosten pro CPU-Kern-Stunde
- **RAM-Nutzung**: Kosten pro GB-Stunde

#### 3.1.2 Speicherressourcen

- **Temporärer Speicher**: Kosten für temporären Speicher während der Analyse
- **Persistenter Speicher**: Kosten für die langfristige Speicherung von Ergebnissen
- **Datenübertragung**: Kosten für ein- und ausgehenden Datenverkehr

#### 3.1.3 Externe Dienste

- **API-Aufrufe**: Kosten für Aufrufe externer APIs (z.B. Spracherkennung, Übersetzung)
- **Spezielle Modelle**: Kosten für die Nutzung kostenpflichtiger ML-Modelle

#### 3.1.4 Betriebskosten

- **Verwaltungsaufwand**: Anteil an den allgemeinen Betriebskosten
- **Support**: Kosten für technischen Support und Wartung

### 3.2 Berechnungsmodell

Die Gesamtkosten werden nach folgender Formel berechnet:

```
Gesamtkosten = Rechenkosten + Speicherkosten + Dienstkosten + Betriebskosten
```

Wobei:

```
Rechenkosten = Σ (GPU-Stunden × GPU-Preis) + Σ (CPU-Stunden × CPU-Preis) + Σ (RAM-GB-Stunden × RAM-Preis)

Speicherkosten = (Temp-Speicher-GB × Temp-Speicher-Preis) + (Persist-Speicher-GB × Persist-Speicher-Preis × Speicherdauer) + (Datenübertragung-GB × Datenübertragungspreis)

Dienstkosten = Σ (API-Aufrufe × API-Preis) + Σ (Modellnutzung × Modellpreis)

Betriebskosten = Basisgebühr + (Gesamtkosten × Verwaltungsprozentsatz)
```

## 4. Implementierung

### 4.1 Kostenschätzungsmodul

Das Kostenschätzungsmodul ist verantwortlich für die Berechnung und Bereitstellung von Kostenschätzungen:

```python
class CostEstimator:
    def __init__(self, pricing_service, resource_estimator, historical_analyzer):
        self.pricing_service = pricing_service
        self.resource_estimator = resource_estimator
        self.historical_analyzer = historical_analyzer
        self.cost_models = self._load_cost_models()
    
    def _load_cost_models(self):
        """Lädt die aktuellen Kostenmodelle."""
        return {
            "compute": self.pricing_service.get_compute_pricing(),
            "storage": self.pricing_service.get_storage_pricing(),
            "services": self.pricing_service.get_service_pricing(),
            "operations": self.pricing_service.get_operations_pricing()
        }
    
    def estimate_cost(self, job_config, input_metadata):
        """Schätzt die Kosten für einen Job basierend auf Konfiguration und Eingabedaten."""
        try:
            # 1. Schätze den Ressourcenbedarf
            resource_estimates = self.resource_estimator.estimate_resources(job_config, input_metadata)
            
            # 2. Berechne die Kosten für jede Komponente
            compute_costs = self._calculate_compute_costs(resource_estimates)
            storage_costs = self._calculate_storage_costs(resource_estimates, job_config)
            service_costs = self._calculate_service_costs(job_config)
            operation_costs = self._calculate_operation_costs(compute_costs, storage_costs, service_costs)
            
            # 3. Berechne die Gesamtkosten
            total_cost = compute_costs["total"] + storage_costs["total"] + service_costs["total"] + operation_costs["total"]
            
            # 4. Wende historische Korrekturen an
            adjusted_cost = self._apply_historical_corrections(total_cost, job_config, input_metadata)
            
            # 5. Erstelle die detaillierte Kostenaufschlüsselung
            cost_breakdown = {
                "total": adjusted_cost,
                "compute": compute_costs,
                "storage": storage_costs,
                "services": service_costs,
                "operations": operation_costs,
                "confidence": self._calculate_confidence(job_config, input_metadata),
                "optimization_suggestions": self._generate_optimization_suggestions(job_config, resource_estimates)
            }
            
            return {
                "success": True,
                "cost_estimate": cost_breakdown
            }
        
        except Exception as e:
            logging.error(f"Failed to estimate cost: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _calculate_compute_costs(self, resource_estimates):
        """Berechnet die Kosten für Rechenressourcen."""
        compute_costs = {
            "gpu": {},
            "cpu": {},
            "ram": {},
            "total": 0
        }
        
        # GPU-Kosten
        for gpu_type, hours in resource_estimates["gpu"].items():
            price = self.cost_models["compute"]["gpu"].get(gpu_type, 0)
            cost = hours * price
            compute_costs["gpu"][gpu_type] = {
                "hours": hours,
                "price_per_hour": price,
                "cost": cost
            }
            compute_costs["total"] += cost
        
        # CPU-Kosten
        cpu_hours = resource_estimates["cpu"]["hours"]
        cpu_price = self.cost_models["compute"]["cpu"]["price_per_core_hour"]
        cpu_cost = cpu_hours * cpu_price
        compute_costs["cpu"] = {
            "hours": cpu_hours,
            "price_per_hour": cpu_price,
            "cost": cpu_cost
        }
        compute_costs["total"] += cpu_cost
        
        # RAM-Kosten
        ram_gb_hours = resource_estimates["ram"]["gb_hours"]
        ram_price = self.cost_models["compute"]["ram"]["price_per_gb_hour"]
        ram_cost = ram_gb_hours * ram_price
        compute_costs["ram"] = {
            "gb_hours": ram_gb_hours,
            "price_per_gb_hour": ram_price,
            "cost": ram_cost
        }
        compute_costs["total"] += ram_cost
        
        return compute_costs
    
    def _calculate_storage_costs(self, resource_estimates, job_config):
        """Berechnet die Kosten für Speicherressourcen."""
        storage_costs = {
            "temporary": {},
            "persistent": {},
            "transfer": {},
            "total": 0
        }
        
        # Temporärer Speicher
        temp_gb = resource_estimates["storage"]["temporary_gb"]
        temp_price = self.cost_models["storage"]["temporary"]["price_per_gb"]
        temp_cost = temp_gb * temp_price
        storage_costs["temporary"] = {
            "gb": temp_gb,
            "price_per_gb": temp_price,
            "cost": temp_cost
        }
        storage_costs["total"] += temp_cost
        
        # Persistenter Speicher
        persist_gb = resource_estimates["storage"]["persistent_gb"]
        persist_price = self.cost_models["storage"]["persistent"]["price_per_gb_month"]
        retention_months = job_config.get("result_retention_months", 1)
        persist_cost = persist_gb * persist_price * retention_months
        storage_costs["persistent"] = {
            "gb": persist_gb,
            "price_per_gb_month": persist_price,
            "retention_months": retention_months,
            "cost": persist_cost
        }
        storage_costs["total"] += persist_cost
        
        # Datenübertragung
        transfer_gb = resource_estimates["storage"]["transfer_gb"]
        transfer_price = self.cost_models["storage"]["transfer"]["price_per_gb"]
        transfer_cost = transfer_gb * transfer_price
        storage_costs["transfer"] = {
            "gb": transfer_gb,
            "price_per_gb": transfer_price,
            "cost": transfer_cost
        }
        storage_costs["total"] += transfer_cost
        
        return storage_costs
    
    def _calculate_service_costs(self, job_config):
        """Berechnet die Kosten für externe Dienste."""
        service_costs = {
            "api_calls": {},
            "models": {},
            "total": 0
        }
        
        # API-Aufrufe
        for api, calls in job_config.get("api_calls", {}).items():
            if api in self.cost_models["services"]["api"]:
                price = self.cost_models["services"]["api"][api]["price_per_call"]
                cost = calls * price
                service_costs["api_calls"][api] = {
                    "calls": calls,
                    "price_per_call": price,
                    "cost": cost
                }
                service_costs["total"] += cost
        
        # Spezielle Modelle
        for model, usage in job_config.get("models", {}).items():
            if model in self.cost_models["services"]["models"]:
                price = self.cost_models["services"]["models"][model]["price_per_use"]
                cost = usage * price
                service_costs["models"][model] = {
                    "usage": usage,
                    "price_per_use": price,
                    "cost": cost
                }
                service_costs["total"] += cost
        
        return service_costs
    
    def _calculate_operation_costs(self, compute_costs, storage_costs, service_costs):
        """Berechnet die Betriebskosten."""
        subtotal = compute_costs["total"] + storage_costs["total"] + service_costs["total"]
        
        base_fee = self.cost_models["operations"]["base_fee"]
        management_percentage = self.cost_models["operations"]["management_percentage"]
        management_cost = subtotal * management_percentage
        
        return {
            "base_fee": base_fee,
            "management": {
                "percentage": management_percentage,
                "cost": management_cost
            },
            "total": base_fee + management_cost
        }
    
    def _apply_historical_corrections(self, total_cost, job_config, input_metadata):
        """Wendet Korrekturen basierend auf historischen Daten an."""
        correction_factor = self.historical_analyzer.get_correction_factor(job_config, input_metadata)
        return total_cost * correction_factor
    
    def _calculate_confidence(self, job_config, input_metadata):
        """Berechnet die Konfidenz der Kostenschätzung."""
        return self.historical_analyzer.get_confidence_score(job_config, input_metadata)
    
    def _generate_optimization_suggestions(self, job_config, resource_estimates):
        """Generiert Vorschläge zur Kostenoptimierung."""
        suggestions = []
        
        # Prüfe auf überdimensionierte GPU-Ressourcen
        if resource_estimates["gpu_utilization"] < 0.7:
            suggestions.append({
                "type": "gpu_downgrade",
                "description": "Erwägen Sie die Verwendung einer kostengünstigeren GPU, da die geschätzte Auslastung unter 70% liegt.",
                "potential_savings": "15-30%"
            })
        
        # Prüfe auf optimierbare Speichernutzung
        if resource_estimates["storage"]["persistent_gb"] > 100:
            suggestions.append({
                "type": "storage_optimization",
                "description": "Aktivieren Sie die Komprimierung für persistente Daten, um Speicherkosten zu reduzieren.",
                "potential_savings": "20-40%"
            })
        
        # Prüfe auf optimierbare Modulkonfiguration
        for module, config in job_config.get("modules", {}).items():
            if module == "video_analysis" and config.get("resolution", "original") == "original":
                suggestions.append({
                    "type": "resolution_reduction",
                    "description": "Reduzieren Sie die Videoauflösung für die Analyse, um Rechenkosten zu senken.",
                    "potential_savings": "10-25%"
                })
        
        return suggestions
```

### 4.2 Ressourcenschätzungsmodul

Das Ressourcenschätzungsmodul prognostiziert den Ressourcenbedarf basierend auf den Eingabedaten und der Jobkonfiguration:

```python
class ResourceEstimator:
    def __init__(self, model_registry, historical_data_service):
        self.model_registry = model_registry
        self.historical_data = historical_data_service
        self.estimation_models = self._load_estimation_models()
    
    def _load_estimation_models(self):
        """Lädt die Modelle zur Ressourcenschätzung."""
        return {
            "video": self.model_registry.get_model("video_resource_estimator"),
            "audio": self.model_registry.get_model("audio_resource_estimator"),
            "image": self.model_registry.get_model("image_resource_estimator"),
            "text": self.model_registry.get_model("text_resource_estimator"),
            "multimodal": self.model_registry.get_model("multimodal_resource_estimator")
        }
    
    def estimate_resources(self, job_config, input_metadata):
        """Schätzt den Ressourcenbedarf für einen Job."""
        # Bestimme den Medientyp
        media_type = self._determine_media_type(input_metadata)
        
        # Wähle das entsprechende Schätzungsmodell
        if media_type in self.estimation_models:
            estimator = self.estimation_models[media_type]
        else:
            estimator = self.estimation_models["multimodal"]
        
        # Extrahiere relevante Features für die Schätzung
        features = self._extract_features(job_config, input_metadata)
        
        # Führe die Schätzung durch
        raw_estimates = estimator.predict(features)
        
        # Wende Korrekturen basierend auf historischen Daten an
        corrected_estimates = self._apply_historical_corrections(raw_estimates, job_config, input_metadata)
        
        # Strukturiere die Ergebnisse
        return self._format_estimates(corrected_estimates, job_config)
    
    def _determine_media_type(self, input_metadata):
        """Bestimmt den Hauptmedientyp der Eingabedaten."""
        media_counts = {
            "video": 0,
            "audio": 0,
            "image": 0,
            "text": 0
        }
        
        for item in input_metadata:
            media_type = item.get("type", "unknown").lower()
            if media_type in media_counts:
                media_counts[media_type] += 1
        
        # Bestimme den häufigsten Medientyp
        max_count = 0
        main_type = "multimodal"
        
        for media_type, count in media_counts.items():
            if count > max_count:
                max_count = count
                main_type = media_type
        
        # Wenn mehrere Typen vorhanden sind, verwende "multimodal"
        if sum(1 for count in media_counts.values() if count > 0) > 1:
            return "multimodal"
        
        return main_type
    
    def _extract_features(self, job_config, input_metadata):
        """Extrahiert Features für die Ressourcenschätzung."""
        features = {
            # Job-Konfiguration
            "modules": list(job_config.get("modules", {}).keys()),
            "parallel_processing": job_config.get("parallel_processing", False),
            "priority": job_config.get("priority", "normal"),
            
            # Eingabedaten
            "total_items": len(input_metadata),
            "total_duration_seconds": 0,
            "total_size_bytes": 0,
            "max_resolution": [0, 0],
            "media_types": {}
        }
        
        # Sammle Informationen über die Eingabedaten
        for item in input_metadata:
            # Größe
            size_bytes = item.get("size_bytes", 0)
            features["total_size_bytes"] += size_bytes
            
            # Medientyp
            media_type = item.get("type", "unknown").lower()
            if media_type not in features["media_types"]:
                features["media_types"][media_type] = 0
            features["media_types"][media_type] += 1
            
            # Spezifische Eigenschaften je nach Medientyp
            if media_type == "video":
                # Dauer
                duration = item.get("duration_seconds", 0)
                features["total_duration_seconds"] += duration
                
                # Auflösung
                width = item.get("width", 0)
                height = item.get("height", 0)
                if width * height > features["max_resolution"][0] * features["max_resolution"][1]:
                    features["max_resolution"] = [width, height]
                
                # Framerate
                fps = item.get("fps", 0)
                if "max_fps" not in features or fps > features["max_fps"]:
                    features["max_fps"] = fps
            
            elif media_type == "audio":
                # Dauer
                duration = item.get("duration_seconds", 0)
                features["total_duration_seconds"] += duration
                
                # Abtastrate
                sample_rate = item.get("sample_rate", 0)
                if "max_sample_rate" not in features or sample_rate > features["max_sample_rate"]:
                    features["max_sample_rate"] = sample_rate
            
            elif media_type == "image":
                # Auflösung
                width = item.get("width", 0)
                height = item.get("height", 0)
                if width * height > features["max_resolution"][0] * features["max_resolution"][1]:
                    features["max_resolution"] = [width, height]
        
        return features
    
    def _apply_historical_corrections(self, raw_estimates, job_config, input_metadata):
        """Wendet Korrekturen basierend auf historischen Daten an."""
        # Suche nach ähnlichen Jobs in der Vergangenheit
        similar_jobs = self.historical_data.find_similar_jobs(job_config, input_metadata)
        
        if not similar_jobs:
            return raw_estimates
        
        # Berechne Korrekturfaktoren basierend auf historischen Daten
        correction_factors = {
            "gpu_hours": [],
            "cpu_hours": [],
            "ram_gb_hours": [],
            "temporary_storage_gb": [],
            "persistent_storage_gb": [],
            "transfer_gb": []
        }
        
        for job in similar_jobs:
            actual = job["actual_resources"]
            estimated = job["estimated_resources"]
            
            for key in correction_factors.keys():
                if key in actual and key in estimated and estimated[key] > 0:
                    factor = actual[key] / estimated[key]
                    correction_factors[key].append(factor)
        
        # Berechne den Median der Korrekturfaktoren
        median_factors = {}
        for key, factors in correction_factors.items():
            if factors:
                median_factors[key] = statistics.median(factors)
            else:
                median_factors[key] = 1.0
        
        # Wende die Korrekturfaktoren an
        corrected_estimates = {}
        for key, value in raw_estimates.items():
            if key in median_factors:
                corrected_estimates[key] = value * median_factors[key]
            else:
                corrected_estimates[key] = value
        
        return corrected_estimates
    
    def _format_estimates(self, estimates, job_config):
        """Formatiert die Schätzungen in eine strukturierte Form."""
        # Bestimme den GPU-Typ basierend auf der Jobkonfiguration
        gpu_type = job_config.get("gpu_type", "t4")
        
        # Strukturiere die Schätzungen
        formatted = {
            "gpu": {
                gpu_type: estimates.get("gpu_hours", 0)
            },
            "cpu": {
                "hours": estimates.get("cpu_hours", 0)
            },
            "ram": {
                "gb_hours": estimates.get("ram_gb_hours", 0)
            },
            "storage": {
                "temporary_gb": estimates.get("temporary_storage_gb", 0),
                "persistent_gb": estimates.get("persistent_storage_gb", 0),
                "transfer_gb": estimates.get("transfer_gb", 0)
            },
            "duration": {
                "estimated_hours": estimates.get("duration_hours", 0)
            },
            "gpu_utilization": estimates.get("gpu_utilization", 0.8)
        }
        
        return formatted
```

### 4.3 Historischer Datenanalysator

Der Historische Datenanalysator verbessert die Genauigkeit der Kostenschätzungen durch Analyse früherer Jobs:

```python
class HistoricalAnalyzer:
    def __init__(self, database_client, similarity_engine):
        self.db = database_client
        self.similarity_engine = similarity_engine
    
    def get_correction_factor(self, job_config, input_metadata):
        """Ermittelt einen Korrekturfaktor basierend auf historischen Daten."""
        similar_jobs = self.find_similar_jobs(job_config, input_metadata)
        
        if not similar_jobs:
            return 1.0
        
        # Berechne den Korrekturfaktor als Verhältnis von tatsächlichen zu geschätzten Kosten
        factors = []
        for job in similar_jobs:
            if job["estimated_cost"] > 0:
                factor = job["actual_cost"] / job["estimated_cost"]
                factors.append(factor)
        
        if not factors:
            return 1.0
        
        # Verwende den Median, um Ausreißer zu vermeiden
        return statistics.median(factors)
    
    def get_confidence_score(self, job_config, input_metadata):
        """Berechnet einen Konfidenzwert für die Kostenschätzung."""
        similar_jobs = self.find_similar_jobs(job_config, input_metadata)
        
        if not similar_jobs:
            return 0.5  # Mittlere Konfidenz bei fehlenden historischen Daten
        
        # Berechne die durchschnittliche Abweichung zwischen geschätzten und tatsächlichen Kosten
        deviations = []
        for job in similar_jobs:
            if job["estimated_cost"] > 0:
                deviation = abs(job["actual_cost"] - job["estimated_cost"]) / job["estimated_cost"]
                deviations.append(deviation)
        
        if not deviations:
            return 0.5
        
        # Berechne die Konfidenz basierend auf der durchschnittlichen Abweichung
        avg_deviation = statistics.mean(deviations)
        confidence = max(0, min(1, 1 - avg_deviation))
        
        return confidence
    
    def find_similar_jobs(self, job_config, input_metadata, limit=10):
        """Findet ähnliche Jobs in der Vergangenheit."""
        # Extrahiere Features für den Ähnlichkeitsvergleich
        features = self._extract_similarity_features(job_config, input_metadata)
        
        # Suche nach ähnlichen Jobs in der Datenbank
        similar_jobs = self.similarity_engine.find_similar(
            collection="completed_jobs",
            features=features,
            limit=limit,
            min_similarity=0.7
        )
        
        # Filtere Jobs ohne Kosteninformationen
        filtered_jobs = []
        for job in similar_jobs:
            if "estimated_cost" in job and "actual_cost" in job:
                filtered_jobs.append(job)
        
        return filtered_jobs
    
    def _extract_similarity_features(self, job_config, input_metadata):
        """Extrahiert Features für den Ähnlichkeitsvergleich."""
        features = {
            # Job-Konfiguration
            "modules": list(job_config.get("modules", {}).keys()),
            "parallel_processing": job_config.get("parallel_processing", False),
            
            # Eingabedaten
            "media_types": {},
            "total_items": len(input_metadata),
            "total_duration_seconds": 0,
            "total_size_bytes": 0
        }
        
        # Sammle Informationen über die Eingabedaten
        for item in input_metadata:
            # Medientyp
            media_type = item.get("type", "unknown").lower()
            if media_type not in features["media_types"]:
                features["media_types"][media_type] = 0
            features["media_types"][media_type] += 1
            
            # Größe
            size_bytes = item.get("size_bytes", 0)
            features["total_size_bytes"] += size_bytes
            
            # Dauer (für Video und Audio)
            if media_type in ["video", "audio"]:
                duration = item.get("duration_seconds", 0)
                features["total_duration_seconds"] += duration
        
        return features
```

### 4.4 Preisservice

Der Preisservice verwaltet die aktuellen Preise für verschiedene Ressourcen und Dienste:

```python
class PricingService:
    def __init__(self, database_client, config_service):
        self.db = database_client
        self.config = config_service
        self.cache = {}
        self.cache_expiry = {}
        self.cache_ttl = 3600  # 1 Stunde
    
    def get_compute_pricing(self):
        """Ruft die aktuellen Preise für Rechenressourcen ab."""
        return self._get_cached_pricing("compute")
    
    def get_storage_pricing(self):
        """Ruft die aktuellen Preise für Speicherressourcen ab."""
        return self._get_cached_pricing("storage")
    
    def get_service_pricing(self):
        """Ruft die aktuellen Preise für externe Dienste ab."""
        return self._get_cached_pricing("services")
    
    def get_operations_pricing(self):
        """Ruft die aktuellen Preise für Betriebskosten ab."""
        return self._get_cached_pricing("operations")
    
    def _get_cached_pricing(self, category):
        """Ruft Preise aus dem Cache oder der Datenbank ab."""
        now = time.time()
        
        # Prüfe, ob die Preise im Cache sind und noch gültig
        if category in self.cache and self.cache_expiry.get(category, 0) > now:
            return self.cache[category]
        
        # Lade die Preise aus der Datenbank
        pricing = self._load_pricing_from_db(category)
        
        # Aktualisiere den Cache
        self.cache[category] = pricing
        self.cache_expiry[category] = now + self.cache_ttl
        
        return pricing
    
    def _load_pricing_from_db(self, category):
        """Lädt die Preise aus der Datenbank."""
        pricing_doc = self.db.pricing.find_one({"category": category})
        
        if not pricing_doc:
            # Verwende Standardpreise, wenn keine in der Datenbank gefunden wurden
            return self._get_default_pricing(category)
        
        return pricing_doc["pricing"]
    
    def _get_default_pricing(self, category):
        """Gibt Standardpreise zurück."""
        if category == "compute":
            return {
                "gpu": {
                    "t4": 0.35,      # $ pro Stunde
                    "v100": 0.90,    # $ pro Stunde
                    "a100": 1.50     # $ pro Stunde
                },
                "cpu": {
                    "price_per_core_hour": 0.05  # $ pro Kern-Stunde
                },
                "ram": {
                    "price_per_gb_hour": 0.01    # $ pro GB-Stunde
                }
            }
        
        elif category == "storage":
            return {
                "temporary": {
                    "price_per_gb": 0.05  # $ pro GB
                },
                "persistent": {
                    "price_per_gb_month": 0.02  # $ pro GB-Monat
                },
                "transfer": {
                    "price_per_gb": 0.10  # $ pro GB
                }
            }
        
        elif category == "services":
            return {
                "api": {
                    "speech_recognition": {
                        "price_per_call": 0.006  # $ pro Minute
                    },
                    "translation": {
                        "price_per_call": 0.001  # $ pro 100 Zeichen
                    }
                },
                "models": {
                    "premium_face_recognition": {
                        "price_per_use": 0.01  # $ pro Gesicht
                    },
                    "premium_object_detection": {
                        "price_per_use": 0.005  # $ pro Bild
                    }
                }
            }
        
        elif category == "operations":
            return {
                "base_fee": 1.0,  # $ Basisgebühr pro Job
                "management_percentage": 0.05  # 5% Verwaltungsgebühr
            }
        
        return {}
    
    def update_pricing(self, category, new_pricing):
        """Aktualisiert die Preise in der Datenbank."""
        # Aktualisiere die Datenbank
        self.db.pricing.update_one(
            {"category": category},
            {"$set": {"pricing": new_pricing, "updated_at": datetime.now()}},
            upsert=True
        )
        
        # Aktualisiere den Cache
        self.cache[category] = new_pricing
        self.cache_expiry[category] = time.time() + self.cache_ttl
        
        return {"success": True}
```

## 5. Benutzeroberfläche

### 5.1 Kostenschätzungskomponente

Die Benutzeroberfläche bietet eine interaktive Komponente zur Anzeige und Anpassung der Kostenschätzung:

```typescript
// React-Komponente für die Kostenschätzung
import React, { useState, useEffect } from 'react';
import { 
  Card, CardContent, Typography, Divider, Grid, Chip, 
  CircularProgress, Accordion, AccordionSummary, 
  AccordionDetails, Button, Tooltip, Alert, Box
} from '@mui/material';
import { 
  ExpandMore as ExpandMoreIcon,
  AttachMoney as MoneyIcon,
  Info as InfoIcon,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Lightbulb as LightbulbIcon
} from '@mui/icons-material';
import { estimateJobCost } from '../api/costEstimationService';

interface CostEstimationProps {
  jobConfig: any;
  inputMetadata: any[];
  onConfigChange?: (newConfig: any) => void;
}

const CostEstimation: React.FC<CostEstimationProps> = ({ 
  jobConfig, 
  inputMetadata,
  onConfigChange 
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [costEstimate, setCostEstimate] = useState<any>(null);
  
  // Aktualisiere die Kostenschätzung, wenn sich die Konfiguration oder Eingabedaten ändern
  useEffect(() => {
    updateCostEstimate();
  }, [jobConfig, inputMetadata]);
  
  const updateCostEstimate = async () => {
    if (!jobConfig || !inputMetadata || inputMetadata.length === 0) {
      return;
    }
    
    setLoading(true);
    setError('');
    
    try {
      const result = await estimateJobCost(jobConfig, inputMetadata);
      if (result.success) {
        setCostEstimate(result.cost_estimate);
      } else {
        setError(result.error || 'Failed to estimate cost');
        setCostEstimate(null);
      }
    } catch (err) {
      setError('An error occurred while estimating cost');
      setCostEstimate(null);
    } finally {
      setLoading(false);
    }
  };
  
  const applyOptimizationSuggestion = (suggestion: any) => {
    if (!onConfigChange || !jobConfig) return;
    
    const newConfig = { ...jobConfig };
    
    switch (suggestion.type) {
      case 'gpu_downgrade':
        // Ändere den GPU-Typ zu einem kostengünstigeren
        if (newConfig.gpu_type === 'a100') {
          newConfig.gpu_type = 'v100';
        } else if (newConfig.gpu_type === 'v100') {
          newConfig.gpu_type = 't4';
        }
        break;
        
      case 'resolution_reduction':
        // Reduziere die Videoauflösung
        if (newConfig.modules && newConfig.modules.video_analysis) {
          newConfig.modules.video_analysis.resolution = '720p';
        }
        break;
        
      case 'storage_optimization':
        // Aktiviere Komprimierung
        newConfig.compress_results = true;
        break;
    }
    
    onConfigChange(newConfig);
  };
  
  const renderConfidenceIndicator = (confidence: number) => {
    let color = 'error';
    let label = 'Niedrig';
    
    if (confidence >= 0.8) {
      color = 'success';
      label = 'Hoch';
    } else if (confidence >= 0.5) {
      color = 'warning';
      label = 'Mittel';
    }
    
    return (
      <Tooltip title={`Konfidenz der Kostenschätzung: ${Math.round(confidence * 100)}%`}>
        <Chip 
          icon={<InfoIcon />} 
          label={label} 
          color={color as any} 
          size="small" 
          variant="outlined" 
        />
      </Tooltip>
    );
  };
  
  if (loading) {
    return (
      <Card>
        <CardContent style={{ textAlign: 'center', padding: 20 }}>
          <CircularProgress size={40} />
          <Typography variant="body1" style={{ marginTop: 10 }}>
            Kosten werden berechnet...
          </Typography>
        </CardContent>
      </Card>
    );
  }
  
  if (error) {
    return (
      <Alert severity="error">
        {error}
      </Alert>
    );
  }
  
  if (!costEstimate) {
    return (
      <Card>
        <CardContent>
          <Typography variant="body1">
            Keine Kostenschätzung verfügbar. Bitte konfigurieren Sie den Job und fügen Sie Eingabedaten hinzu.
          </Typography>
        </CardContent>
      </Card>
    );
  }
  
  return (
    <Card>
      <CardContent>
        <Grid container spacing={2} alignItems="center">
          <Grid item>
            <MoneyIcon fontSize="large" color="primary" />
          </Grid>
          <Grid item xs>
            <Typography variant="h5" component="div">
              Geschätzte Kosten: ${costEstimate.total.toFixed(2)}
            </Typography>
          </Grid>
          <Grid item>
            {renderConfidenceIndicator(costEstimate.confidence)}
          </Grid>
        </Grid>
        
        {costEstimate.optimization_suggestions && costEstimate.optimization_suggestions.length > 0 && (
          <Box mt={2}>
            <Alert 
              severity="info" 
              icon={<LightbulbIcon />}
              action={
                <Button 
                  color="inherit" 
                  size="small" 
                  onClick={() => applyOptimizationSuggestion(costEstimate.optimization_suggestions[0])}
                >
                  Anwenden
                </Button>
              }
            >
              <Typography variant="body2">
                {costEstimate.optimization_suggestions[0].description}
                <br />
                <strong>Potenzielle Einsparung:</strong> {costEstimate.optimization_suggestions[0].potential_savings}
              </Typography>
            </Alert>
          </Box>
        )}
        
        <Divider style={{ margin: '16px 0' }} />
        
        <Accordion>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography>Kostenaufschlüsselung</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6}>
                <Typography variant="subtitle2">Rechenressourcen</Typography>
                <Typography variant="body2">
                  GPU: ${costEstimate.compute.total.toFixed(2)}
                </Typography>
                {Object.entries(costEstimate.compute.gpu).map(([type, data]: [string, any]) => (
                  <Typography variant="body2" key={type} color="textSecondary">
                    {type.toUpperCase()}: {data.hours.toFixed(2)} Stunden × ${data.price_per_hour}/h = ${data.cost.toFixed(2)}
                  </Typography>
                ))}
                <Typography variant="body2">
                  CPU: ${costEstimate.compute.cpu.cost.toFixed(2)}
                </Typography>
                <Typography variant="body2">
                  RAM: ${costEstimate.compute.ram.cost.toFixed(2)}
                </Typography>
              </Grid>
              
              <Grid item xs={12} sm={6}>
                <Typography variant="subtitle2">Speicherressourcen</Typography>
                <Typography variant="body2">
                  Temporär: ${costEstimate.storage.temporary.cost.toFixed(2)}
                </Typography>
                <Typography variant="body2">
                  Persistent: ${costEstimate.storage.persistent.cost.toFixed(2)}
                </Typography>
                <Typography variant="body2">
                  Datenübertragung: ${costEstimate.storage.transfer.cost.toFixed(2)}
                </Typography>
              </Grid>
              
              {costEstimate.services.total > 0 && (
                <Grid item xs={12} sm={6}>
                  <Typography variant="subtitle2">Externe Dienste</Typography>
                  {Object.entries(costEstimate.services.api_calls).map(([api, data]: [string, any]) => (
                    <Typography variant="body2" key={api}>
                      {api}: ${data.cost.toFixed(2)}
                    </Typography>
                  ))}
                  {Object.entries(costEstimate.services.models).map(([model, data]: [string, any]) => (
                    <Typography variant="body2" key={model}>
                      {model}: ${data.cost.toFixed(2)}
                    </Typography>
                  ))}
                </Grid>
              )}
              
              <Grid item xs={12} sm={6}>
                <Typography variant="subtitle2">Betriebskosten</Typography>
                <Typography variant="body2">
                  Basisgebühr: ${costEstimate.operations.base_fee.toFixed(2)}
                </Typography>
                <Typography variant="body2">
                  Verwaltung ({(costEstimate.operations.management.percentage * 100).toFixed(0)}%): ${costEstimate.operations.management.cost.toFixed(2)}
                </Typography>
              </Grid>
            </Grid>
          </AccordionDetails>
        </Accordion>
        
        <Accordion>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography>Geschätzte Laufzeit</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Typography variant="body1">
              Voraussichtliche Dauer: {costEstimate.duration.estimated_hours.toFixed(2)} Stunden
            </Typography>
          </AccordionDetails>
        </Accordion>
        
        {costEstimate.optimization_suggestions && costEstimate.optimization_suggestions.length > 0 && (
          <Accordion>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography>Optimierungsvorschläge</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Grid container spacing={2}>
                {costEstimate.optimization_suggestions.map((suggestion: any, index: number) => (
                  <Grid item xs={12} key={index}>
                    <Alert 
                      severity="info" 
                      icon={<LightbulbIcon />}
                      action={
                        onConfigChange && (
                          <Button 
                            color="primary" 
                            size="small" 
                            onClick={() => applyOptimizationSuggestion(suggestion)}
                          >
                            Anwenden
                          </Button>
                        )
                      }
                    >
                      <Typography variant="body2">
                        {suggestion.description}
                        <br />
                        <strong>Potenzielle Einsparung:</strong> {suggestion.potential_savings}
                      </Typography>
                    </Alert>
                  </Grid>
                ))}
              </Grid>
            </AccordionDetails>
          </Accordion>
        )}
      </CardContent>
    </Card>
  );
};

export default CostEstimation;
```

## 6. API-Endpunkte

Das System bietet folgende API-Endpunkte für die Kostenschätzung:

```python
# FastAPI-Endpunkte für die Kostenschätzung
from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List, Dict, Any
from .services.cost_estimator import CostEstimator
from .auth.auth_handler import get_current_user

router = APIRouter(prefix="/api/cost", tags=["cost"])

@router.post("/estimate")
async def estimate_cost(
    job_config: Dict[str, Any] = Body(...),
    input_metadata: List[Dict[str, Any]] = Body(...),
    current_user = Depends(get_current_user),
    cost_estimator: CostEstimator = Depends()
):
    """Schätzt die Kosten für einen Job basierend auf Konfiguration und Eingabedaten."""
    # Validiere die Eingabedaten
    if not job_config:
        raise HTTPException(status_code=400, detail="Job configuration is required")
    
    if not input_metadata:
        raise HTTPException(status_code=400, detail="Input metadata is required")
    
    # Führe die Kostenschätzung durch
    result = cost_estimator.estimate_cost(job_config, input_metadata)
    
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])
    
    return result

@router.get("/pricing")
async def get_pricing(
    current_user = Depends(get_current_user),
    cost_estimator: CostEstimator = Depends()
):
    """Ruft die aktuellen Preise für verschiedene Ressourcen und Dienste ab."""
    # Prüfe, ob der Benutzer die erforderlichen Berechtigungen hat
    if not current_user["is_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Hole die Preise
    pricing = {
        "compute": cost_estimator.pricing_service.get_compute_pricing(),
        "storage": cost_estimator.pricing_service.get_storage_pricing(),
        "services": cost_estimator.pricing_service.get_service_pricing(),
        "operations": cost_estimator.pricing_service.get_operations_pricing()
    }
    
    return {"success": True, "pricing": pricing}

@router.put("/pricing/{category}")
async def update_pricing(
    category: str,
    pricing: Dict[str, Any] = Body(...),
    current_user = Depends(get_current_user),
    cost_estimator: CostEstimator = Depends()
):
    """Aktualisiert die Preise für eine bestimmte Kategorie."""
    # Prüfe, ob der Benutzer die erforderlichen Berechtigungen hat
    if not current_user["is_admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Validiere die Kategorie
    valid_categories = ["compute", "storage", "services", "operations"]
    if category not in valid_categories:
        raise HTTPException(status_code=400, detail=f"Invalid category. Must be one of: {', '.join(valid_categories)}")
    
    # Aktualisiere die Preise
    result = cost_estimator.pricing_service.update_pricing(category, pricing)
    
    if not result["success"]:
        raise HTTPException(status_code=500, detail="Failed to update pricing")
    
    return {"success": True, "message": f"Pricing for {category} updated successfully"}
```

## 7. Implementierungsplan

### 7.1 Phasen der Implementierung

Die Implementierung des Kostenschätzungsmechanismus erfolgt in drei Phasen:

#### Phase 1: Grundlegende Funktionalität (Monat 1-2)

- Implementierung des Basismodells für die Kostenschätzung
- Einfache Ressourcenschätzung basierend auf Medientyp und -größe
- Grundlegende Benutzeroberfläche für die Anzeige der Kostenschätzung
- API-Endpunkte für die Kostenschätzung

#### Phase 2: Erweiterte Funktionen (Monat 3-4)

- Integration historischer Daten zur Verbesserung der Genauigkeit
- Detaillierte Aufschlüsselung der Kosten nach Komponenten
- Optimierungsvorschläge zur Kostenreduzierung
- Erweiterte Benutzeroberfläche mit interaktiven Elementen

#### Phase 3: Optimierung und Integration (Monat 5-6)

- Feinabstimmung der Schätzungsmodelle basierend auf realen Daten
- Integration mit dem Abrechnungssystem
- Erweiterte Berichterstellung und Analysen
- Umfassende Tests und Fehlerbehebung

### 7.2 Abhängigkeiten und Voraussetzungen

Für die erfolgreiche Implementierung des Kostenschätzungsmechanismus sind folgende Komponenten erforderlich:

- Zuverlässiges Datenbanksystem für die Speicherung historischer Daten
- Zugriff auf aktuelle Preise für Ressourcen und Dienste
- Integration mit dem Job-Management-System
- Integration mit dem Ressourcen-Management-System

## 8. Zusammenfassung

Der Kostenschätzungsmechanismus des AIMA-Systems bietet Benutzern eine präzise und transparente Vorhersage der zu erwartenden Kosten vor der Ausführung von Analysen. Durch die Berücksichtigung verschiedener Faktoren wie Rechenressourcen, Speicherressourcen, externe Dienste und Betriebskosten wird eine umfassende Kostenschätzung ermöglicht.

Die Integration historischer Daten und die kontinuierliche Verbesserung der Schätzungsmodelle gewährleisten eine hohe Genauigkeit der Vorhersagen. Die detaillierte Aufschlüsselung der Kosten und die Optimierungsvorschläge ermöglichen es Benutzern, informierte Entscheidungen zu treffen und ihre Kosten zu optimieren.

Die benutzerfreundliche Oberfläche und die API-Endpunkte bieten flexible Möglichkeiten zur Integration der Kostenschätzung in verschiedene Workflows. Insgesamt trägt der Kostenschätzungsmechanismus wesentlich zur Transparenz, Kostenkontrolle und Benutzerfreundlichkeit des AIMA-Systems bei.