# Abbruchverhalten und Teilergebnismanagement

Dieses Dokument spezifiziert das Verhalten des AIMA-Systems bei verschiedenen Abbruchszenarien, insbesondere in Bezug auf die Behandlung teilweise generierter Ergebnisse und deren Speicherung.

## 1. Übersicht

Das AIMA-System muss robust mit verschiedenen Abbruchszenarien umgehen können, um Datenverlust zu minimieren, Ressourcen effizient zu nutzen und eine positive Benutzererfahrung zu gewährleisten. Dieses Dokument definiert das Systemverhalten bei Benutzerabbrüchen, Systemfehlern und anderen Unterbrechungen von Analyseprozessen.

## 2. Abbruchszenarien

### 2.1 Benutzerinitiierte Abbrüche

Benutzerinitiierte Abbrüche können aus verschiedenen Gründen erfolgen:

- Bewusste Entscheidung, die Analyse zu stoppen (z.B. wegen unerwarteter langer Laufzeit)
- Erkenntnis, dass falsche Parameter oder Daten verwendet wurden
- Änderung der Prioritäten oder Anforderungen während der Analyse
- Versehentlicher Abbruch (z.B. durch Browser-Schließung)

### 2.2 Systeminitiierte Abbrüche

Systeminitiierte Abbrüche können folgende Ursachen haben:

- Kritische Fehler in Analysemodulen
- Ressourcenengpässe (z.B. GPU-Speichermangel)
- Infrastrukturprobleme (z.B. Netzwerkunterbrechungen, Stromausfälle)
- Sicherheitsbedingte Abbrüche (z.B. Erkennung von schädlichem Inhalt)
- Zeitüberschreitungen (z.B. bei Überschreitung maximaler Laufzeit)

### 2.3 Teilabbrüche

Teilabbrüche betreffen nur bestimmte Komponenten des Analyseprozesses:

- Fehler in einzelnen Analysemodulen bei ansonsten funktionierendem Gesamtprozess
- Teilweise Nichtverfügbarkeit von Ressourcen (z.B. Ausfall einzelner GPUs)
- Fehler bei der Verarbeitung bestimmter Medienabschnitte

## 3. Systemverhalten bei Abbrüchen

### 3.1 Grundprinzipien

Das AIMA-System folgt bei Abbrüchen diesen Grundprinzipien:

1. **Datenerhaltung**: Maximale Sicherung bereits generierter Ergebnisse
2. **Transparenz**: Klare Kommunikation des Abbruchstatus an den Benutzer
3. **Ressourcenfreigabe**: Schnelle und vollständige Freigabe nicht mehr benötigter Ressourcen
4. **Wiederaufnahmefähigkeit**: Möglichkeit zur Fortsetzung der Analyse, wo sinnvoll
5. **Konsistenz**: Sicherstellung der Datenintegrität auch bei unvollständigen Ergebnissen

### 3.2 Verhalten bei benutzerinitiiertem Abbruch

Bei einem benutzerinitiiertem Abbruch verhält sich das System wie folgt:

```python
class UserInitiatedAbortHandler:
    def __init__(self, job_id, storage_manager, notification_service):
        self.job_id = job_id
        self.storage_manager = storage_manager
        self.notification_service = notification_service
        self.abort_timestamp = None
    
    def handle_abort(self, user_id, reason=None):
        """Behandelt einen benutzerinitierten Abbruch."""
        self.abort_timestamp = datetime.now()
        
        # 1. Protokolliere den Abbruch
        logging.info(f"User-initiated abort for job {self.job_id} by user {user_id}. Reason: {reason}")
        
        # 2. Signalisiere allen Prozessen den Abbruch
        self._signal_abort_to_processes()
        
        # 3. Warte auf geordnetes Herunterfahren (mit Timeout)
        graceful_shutdown_successful = self._wait_for_graceful_shutdown(timeout_seconds=30)
        
        # 4. Speichere Teilergebnisse
        partial_results = self._save_partial_results()
        
        # 5. Gib Ressourcen frei
        self._release_resources()
        
        # 6. Benachrichtige den Benutzer
        self._notify_user(user_id, partial_results, graceful_shutdown_successful)
        
        # 7. Aktualisiere den Jobstatus
        self._update_job_status(reason, partial_results)
        
        return {
            "status": "aborted",
            "timestamp": self.abort_timestamp,
            "partial_results": partial_results,
            "graceful_shutdown": graceful_shutdown_successful
        }
    
    def _signal_abort_to_processes(self):
        """Sendet Abbruchsignal an alle laufenden Prozesse."""
        # Implementierung des Signalmechanismus an alle Prozesse
        # Verwendet z.B. Kubernetes API, Message Queue oder direkte Prozesssignale
        pass
    
    def _wait_for_graceful_shutdown(self, timeout_seconds):
        """Wartet auf geordnetes Herunterfahren aller Prozesse."""
        start_time = time.time()
        all_processes_stopped = False
        
        while time.time() - start_time < timeout_seconds:
            # Prüfe, ob alle Prozesse ordnungsgemäß heruntergefahren wurden
            all_processes_stopped = self._check_all_processes_stopped()
            if all_processes_stopped:
                break
            time.sleep(1)
        
        if not all_processes_stopped:
            # Erzwinge Beendigung, falls Timeout erreicht
            self._force_terminate_processes()
        
        return all_processes_stopped
    
    def _check_all_processes_stopped(self):
        """Prüft, ob alle Prozesse gestoppt wurden."""
        # Implementierung der Prozessstatusüberprüfung
        pass
    
    def _force_terminate_processes(self):
        """Erzwingt die Beendigung aller noch laufenden Prozesse."""
        # Implementierung der Zwangsbeendigung von Prozessen
        pass
    
    def _save_partial_results(self):
        """Speichert alle verfügbaren Teilergebnisse."""
        # Sammle alle verfügbaren Teilergebnisse aus verschiedenen Quellen
        partial_results = self._collect_partial_results()
        
        # Speichere Teilergebnisse mit Metadaten zum Abbruchzeitpunkt
        result_metadata = {
            "job_id": self.job_id,
            "abort_timestamp": self.abort_timestamp,
            "completion_status": "partial",
            "completed_modules": self._get_completed_modules(),
            "completed_percentage": self._estimate_completion_percentage()
        }
        
        # Speichere in Datenbank mit Abbruchkennzeichnung
        storage_result = self.storage_manager.store_partial_results(
            self.job_id, partial_results, result_metadata
        )
        
        return {
            "result_id": storage_result["result_id"],
            "completed_percentage": result_metadata["completed_percentage"],
            "completed_modules": result_metadata["completed_modules"]
        }
    
    def _collect_partial_results(self):
        """Sammelt alle verfügbaren Teilergebnisse aus verschiedenen Quellen."""
        # Implementierung der Teilergebnissammlung
        pass
    
    def _get_completed_modules(self):
        """Ermittelt, welche Module vollständig abgeschlossen wurden."""
        # Implementierung der Modulstatusermittlung
        pass
    
    def _estimate_completion_percentage(self):
        """Schätzt den Prozentsatz der Fertigstellung."""
        # Implementierung der Fortschrittsschätzung
        pass
    
    def _release_resources(self):
        """Gibt alle vom Job belegten Ressourcen frei."""
        # Implementierung der Ressourcenfreigabe
        pass
    
    def _notify_user(self, user_id, partial_results, graceful_shutdown_successful):
        """Benachrichtigt den Benutzer über den Abbruch und verfügbare Teilergebnisse."""
        notification = {
            "type": "job_aborted",
            "job_id": self.job_id,
            "timestamp": self.abort_timestamp,
            "partial_results_available": bool(partial_results),
            "completed_percentage": partial_results.get("completed_percentage", 0) if partial_results else 0,
            "message": self._generate_user_message(partial_results, graceful_shutdown_successful)
        }
        
        self.notification_service.send_notification(user_id, notification)
    
    def _generate_user_message(self, partial_results, graceful_shutdown_successful):
        """Generiert eine benutzerfreundliche Nachricht über den Abbruchstatus."""
        if not partial_results:
            return "Die Analyse wurde abgebrochen. Es sind keine Teilergebnisse verfügbar."
        
        completed_percentage = partial_results.get("completed_percentage", 0)
        if completed_percentage < 10:
            return "Die Analyse wurde in einem sehr frühen Stadium abgebrochen. Die verfügbaren Teilergebnisse sind möglicherweise nicht aussagekräftig."
        elif completed_percentage < 50:
            return f"Die Analyse wurde bei {completed_percentage}% abgebrochen. Einige Teilergebnisse sind verfügbar, aber möglicherweise unvollständig."
        else:
            return f"Die Analyse wurde bei {completed_percentage}% abgebrochen. Die meisten Ergebnisse sind verfügbar und können eingesehen werden."
    
    def _update_job_status(self, reason, partial_results):
        """Aktualisiert den Jobstatus in der Datenbank."""
        # Implementierung der Jobstatusaktualisierung
        pass
```

### 3.3 Verhalten bei systeminitiiertem Abbruch

Bei einem systeminitiiertem Abbruch verhält sich das System wie folgt:

```python
class SystemInitiatedAbortHandler:
    def __init__(self, job_id, storage_manager, notification_service, error_analyzer):
        self.job_id = job_id
        self.storage_manager = storage_manager
        self.notification_service = notification_service
        self.error_analyzer = error_analyzer
        self.abort_timestamp = None
    
    def handle_abort(self, error_info, severity="critical"):
        """Behandelt einen systeminitiiertem Abbruch."""
        self.abort_timestamp = datetime.now()
        
        # 1. Protokolliere den Fehler und Abbruch
        logging.error(f"System-initiated abort for job {self.job_id}. Error: {error_info}")
        
        # 2. Analysiere den Fehler
        error_analysis = self.error_analyzer.analyze(error_info)
        
        # 3. Entscheide basierend auf der Fehleranalyse
        if error_analysis["recoverable"]:
            return self._handle_recoverable_error(error_analysis)
        else:
            return self._handle_non_recoverable_error(error_analysis)
    
    def _handle_recoverable_error(self, error_analysis):
        """Behandelt einen behebbaren Fehler mit Wiederaufnahmemöglichkeit."""
        # 1. Erstelle Checkpoint für Wiederaufnahme
        checkpoint = self._create_recovery_checkpoint(error_analysis)
        
        # 2. Speichere Teilergebnisse
        partial_results = self._save_partial_results()
        
        # 3. Gib temporär Ressourcen frei
        self._release_resources(temporary=True)
        
        # 4. Plane Wiederaufnahme
        recovery_plan = self._create_recovery_plan(error_analysis, checkpoint)
        
        # 5. Benachrichtige den Benutzer
        self._notify_user_about_recovery(partial_results, recovery_plan)
        
        # 6. Aktualisiere den Jobstatus
        self._update_job_status("paused_for_recovery", error_analysis, recovery_plan)
        
        return {
            "status": "paused_for_recovery",
            "timestamp": self.abort_timestamp,
            "partial_results": partial_results,
            "recovery_plan": recovery_plan,
            "error_analysis": error_analysis
        }
    
    def _handle_non_recoverable_error(self, error_analysis):
        """Behandelt einen nicht behebbaren Fehler ohne Wiederaufnahmemöglichkeit."""
        # 1. Signalisiere allen Prozessen den Abbruch
        self._signal_abort_to_processes()
        
        # 2. Warte auf geordnetes Herunterfahren (mit Timeout)
        self._wait_for_graceful_shutdown(timeout_seconds=30)
        
        # 3. Speichere Teilergebnisse und Fehlerinformationen
        partial_results = self._save_partial_results(include_error_info=True, error_analysis=error_analysis)
        
        # 4. Gib Ressourcen frei
        self._release_resources()
        
        # 5. Benachrichtige den Benutzer
        self._notify_user_about_failure(partial_results, error_analysis)
        
        # 6. Aktualisiere den Jobstatus
        self._update_job_status("failed", error_analysis)
        
        # 7. Löse Fehlerberichterstattung aus
        self._trigger_error_reporting(error_analysis)
        
        return {
            "status": "failed",
            "timestamp": self.abort_timestamp,
            "partial_results": partial_results,
            "error_analysis": error_analysis
        }
    
    def _create_recovery_checkpoint(self, error_analysis):
        """Erstellt einen Checkpoint für die spätere Wiederaufnahme."""
        # Implementierung der Checkpoint-Erstellung
        pass
    
    def _create_recovery_plan(self, error_analysis, checkpoint):
        """Erstellt einen Plan zur Wiederaufnahme der Analyse."""
        # Implementierung der Wiederaufnahmeplanung
        pass
    
    def _notify_user_about_recovery(self, partial_results, recovery_plan):
        """Benachrichtigt den Benutzer über die temporäre Unterbrechung und geplante Wiederaufnahme."""
        # Implementierung der Benutzerbenachrichtigung
        pass
    
    def _notify_user_about_failure(self, partial_results, error_analysis):
        """Benachrichtigt den Benutzer über den endgültigen Abbruch und den Grund."""
        # Implementierung der Benutzerbenachrichtigung
        pass
    
    def _trigger_error_reporting(self, error_analysis):
        """Löst die interne Fehlerberichterstattung aus."""
        # Implementierung der Fehlerberichterstattung
        pass
    
    # Weitere Hilfsmethoden ähnlich wie in UserInitiatedAbortHandler
    # ...
```

### 3.4 Verhalten bei Teilabbrüchen

Bei Teilabbrüchen versucht das System, die Analyse mit reduzierten Funktionen fortzusetzen:

```python
class PartialAbortHandler:
    def __init__(self, job_id, module_manager, storage_manager, notification_service):
        self.job_id = job_id
        self.module_manager = module_manager
        self.storage_manager = storage_manager
        self.notification_service = notification_service
        self.partial_abort_timestamp = None
    
    def handle_partial_abort(self, module_id, error_info):
        """Behandelt einen Teilabbruch eines spezifischen Moduls."""
        self.partial_abort_timestamp = datetime.now()
        
        # 1. Protokolliere den Teilabbruch
        logging.warning(f"Partial abort for job {self.job_id}, module {module_id}. Error: {error_info}")
        
        # 2. Bewerte die Auswirkungen des Modulausfalls
        impact_assessment = self._assess_module_failure_impact(module_id)
        
        # 3. Entscheide basierend auf der Auswirkungsbewertung
        if impact_assessment["critical_for_job"]:
            # Wenn das Modul kritisch ist, behandle es als vollständigen Abbruch
            system_abort_handler = SystemInitiatedAbortHandler(
                self.job_id, self.storage_manager, self.notification_service, ErrorAnalyzer()
            )
            return system_abort_handler.handle_abort(
                error_info=f"Critical module {module_id} failed: {error_info}"
            )
        else:
            # Wenn das Modul nicht kritisch ist, setze mit reduzierter Funktionalität fort
            return self._continue_with_reduced_functionality(module_id, impact_assessment)
    
    def _assess_module_failure_impact(self, module_id):
        """Bewertet die Auswirkungen des Ausfalls eines Moduls auf den Gesamtjob."""
        # Hole Modulabhängigkeiten und -kritikalität
        module_info = self.module_manager.get_module_info(module_id)
        dependent_modules = self.module_manager.get_dependent_modules(module_id)
        
        # Prüfe, ob alternative Module verfügbar sind
        alternatives = self.module_manager.get_alternative_modules(module_id)
        
        # Bewerte die Gesamtauswirkung
        critical_for_job = module_info["critical"] and not alternatives
        affected_features = self._identify_affected_features(module_id, dependent_modules)
        quality_impact = self._estimate_quality_impact(module_id, alternatives)
        
        return {
            "critical_for_job": critical_for_job,
            "affected_modules": dependent_modules,
            "affected_features": affected_features,
            "quality_impact": quality_impact,
            "alternatives_available": bool(alternatives),
            "alternatives": alternatives
        }
    
    def _continue_with_reduced_functionality(self, failed_module_id, impact_assessment):
        """Setzt die Analyse mit reduzierter Funktionalität fort."""
        # 1. Rekonfiguriere den Workflow, um das ausgefallene Modul zu umgehen
        if impact_assessment["alternatives_available"]:
            # Verwende ein alternatives Modul, falls verfügbar
            alternative_module = self._select_best_alternative(impact_assessment["alternatives"])
            self._reconfigure_workflow_with_alternative(failed_module_id, alternative_module)
        else:
            # Deaktiviere das ausgefallene Modul und abhängige Funktionen
            self._reconfigure_workflow_without_module(failed_module_id, impact_assessment["affected_modules"])
        
        # 2. Aktualisiere Metadaten und Erwartungen
        self._update_job_metadata_for_reduced_functionality(impact_assessment)
        
        # 3. Benachrichtige den Benutzer
        self._notify_user_about_reduced_functionality(impact_assessment)
        
        # 4. Setze die Verarbeitung fort
        self._resume_processing()
        
        return {
            "status": "continuing_with_reduced_functionality",
            "timestamp": self.partial_abort_timestamp,
            "failed_module": failed_module_id,
            "impact_assessment": impact_assessment,
            "alternative_used": impact_assessment["alternatives_available"]
        }
    
    def _identify_affected_features(self, module_id, dependent_modules):
        """Identifiziert die betroffenen Funktionen und Features."""
        # Implementierung der Feature-Auswirkungsanalyse
        pass
    
    def _estimate_quality_impact(self, module_id, alternatives):
        """Schätzt die Auswirkungen auf die Qualität der Ergebnisse."""
        # Implementierung der Qualitätsauswirkungsschätzung
        pass
    
    def _select_best_alternative(self, alternatives):
        """Wählt die beste Alternative basierend auf Qualität und Verfügbarkeit."""
        # Implementierung der Alternativenauswahl
        pass
    
    def _reconfigure_workflow_with_alternative(self, failed_module_id, alternative_module):
        """Konfiguriert den Workflow neu, um ein alternatives Modul zu verwenden."""
        # Implementierung der Workflow-Rekonfiguration
        pass
    
    def _reconfigure_workflow_without_module(self, failed_module_id, affected_modules):
        """Konfiguriert den Workflow neu, um ohne das ausgefallene Modul fortzufahren."""
        # Implementierung der Workflow-Rekonfiguration
        pass
    
    def _update_job_metadata_for_reduced_functionality(self, impact_assessment):
        """Aktualisiert die Job-Metadaten, um die reduzierte Funktionalität widerzuspiegeln."""
        # Implementierung der Metadatenaktualisierung
        pass
    
    def _notify_user_about_reduced_functionality(self, impact_assessment):
        """Benachrichtigt den Benutzer über die reduzierte Funktionalität."""
        # Implementierung der Benutzerbenachrichtigung
        pass
    
    def _resume_processing(self):
        """Setzt die Verarbeitung mit dem rekonfigurierten Workflow fort."""
        # Implementierung der Verarbeitungsfortsetzung
        pass
```

## 4. Speicherung und Verwaltung von Teilergebnissen

### 4.1 Speicherformat und -struktur

Teilergebnisse werden in einem strukturierten Format gespeichert, das folgende Eigenschaften aufweist:

```python
class PartialResultsManager:
    def __init__(self, database_client, object_storage_client):
        self.db = database_client
        self.object_storage = object_storage_client
    
    def store_partial_results(self, job_id, results, metadata):
        """Speichert Teilergebnisse mit Metadaten."""
        # 1. Erstelle eine eindeutige ID für die Teilergebnisse
        result_id = str(uuid.uuid4())
        
        # 2. Strukturiere die Ergebnisse nach Modulen und Zeitstempeln
        structured_results = self._structure_results(results)
        
        # 3. Speichere große Binärdaten im Objektspeicher
        storage_references = self._store_binary_data(job_id, result_id, structured_results)
        
        # 4. Erstelle den Datenbankdatensatz mit Metadaten und Referenzen
        db_record = {
            "result_id": result_id,
            "job_id": job_id,
            "timestamp": datetime.now(),
            "status": "partial",
            "metadata": metadata,
            "storage_references": storage_references,
            "structured_results": structured_results
        }
        
        # 5. Speichere in der Datenbank
        self.db.partial_results.insert_one(db_record)
        
        return {
            "result_id": result_id,
            "timestamp": db_record["timestamp"],
            "status": "partial"
        }
    
    def _structure_results(self, results):
        """Strukturiert die Ergebnisse nach Modulen und Zeitstempeln."""
        structured = {}
        
        for module_id, module_results in results.items():
            if isinstance(module_results, dict) and "timeline" in module_results:
                # Für zeitbasierte Ergebnisse (z.B. Videoanalyse)
                structured[module_id] = {
                    "type": "timeline",
                    "timeline": self._structure_timeline_results(module_results["timeline"]),
                    "summary": module_results.get("summary", {})
                }
            else:
                # Für nicht-zeitbasierte Ergebnisse
                structured[module_id] = {
                    "type": "simple",
                    "data": module_results
                }
        
        return structured
    
    def _structure_timeline_results(self, timeline_results):
        """Strukturiert zeitbasierte Ergebnisse."""
        # Sortiere nach Zeitstempel und strukturiere
        sorted_timeline = sorted(timeline_results, key=lambda x: x.get("timestamp", 0))
        
        # Gruppiere nach Zeitintervallen für effiziente Abfrage
        intervals = {}
        for item in sorted_timeline:
            timestamp = item.get("timestamp", 0)
            interval_key = int(timestamp / 60) * 60  # Gruppiere pro Minute
            
            if interval_key not in intervals:
                intervals[interval_key] = []
            
            intervals[interval_key].append(item)
        
        return intervals
    
    def _store_binary_data(self, job_id, result_id, structured_results):
        """Speichert große Binärdaten im Objektspeicher und gibt Referenzen zurück."""
        storage_references = {}
        
        for module_id, module_data in structured_results.items():
            module_references = self._process_module_binary_data(job_id, result_id, module_id, module_data)
            if module_references:
                storage_references[module_id] = module_references
        
        return storage_references
    
    def _process_module_binary_data(self, job_id, result_id, module_id, module_data):
        """Verarbeitet Binärdaten eines Moduls und gibt Referenzen zurück."""
        # Implementierung der Binärdatenverarbeitung
        pass
    
    def get_partial_results(self, result_id, include_binary=False):
        """Ruft Teilergebnisse ab, optional mit Binärdaten."""
        # 1. Hole den Datenbankdatensatz
        db_record = self.db.partial_results.find_one({"result_id": result_id})
        if not db_record:
            return None
        
        # 2. Bereite die Basisstruktur vor
        result = {
            "result_id": db_record["result_id"],
            "job_id": db_record["job_id"],
            "timestamp": db_record["timestamp"],
            "status": db_record["status"],
            "metadata": db_record["metadata"],
            "structured_results": db_record["structured_results"]
        }
        
        # 3. Lade Binärdaten, falls angefordert
        if include_binary and "storage_references" in db_record:
            result["binary_data"] = self._load_binary_data(db_record["storage_references"])
        
        return result
    
    def _load_binary_data(self, storage_references):
        """Lädt Binärdaten aus dem Objektspeicher."""
        # Implementierung des Binärdatenladens
        pass
    
    def list_partial_results(self, job_id):
        """Listet alle Teilergebnisse für einen Job auf."""
        results = self.db.partial_results.find({"job_id": job_id}, {
            "result_id": 1,
            "timestamp": 1,
            "status": 1,
            "metadata.completed_percentage": 1,
            "metadata.completed_modules": 1
        })
        
        return list(results)
    
    def delete_partial_results(self, result_id):
        """Löscht Teilergebnisse und zugehörige Binärdaten."""
        # 1. Hole den Datenbankdatensatz
        db_record = self.db.partial_results.find_one({"result_id": result_id})
        if not db_record:
            return False
        
        # 2. Lösche Binärdaten aus dem Objektspeicher
        if "storage_references" in db_record:
            self._delete_binary_data(db_record["storage_references"])
        
        # 3. Lösche den Datenbankdatensatz
        self.db.partial_results.delete_one({"result_id": result_id})
        
        return True
    
    def _delete_binary_data(self, storage_references):
        """Löscht Binärdaten aus dem Objektspeicher."""
        # Implementierung des Binärdatenlöschens
        pass
```

### 4.2 Metadaten für Teilergebnisse

Teilergebnisse werden mit umfangreichen Metadaten versehen, um ihre Interpretation und Verwendung zu erleichtern:

```json
{
  "result_id": "f8e7d6c5-b4a3-42f1-9e8d-7c6b5a4f3d2e",
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp": "2023-06-15T14:32:47.123Z",
  "status": "partial",
  "metadata": {
    "abort_reason": "user_initiated",
    "abort_timestamp": "2023-06-15T14:32:45.789Z",
    "completed_percentage": 67,
    "completed_modules": ["audio_extraction", "speech_recognition", "speaker_diarization"],
    "incomplete_modules": ["emotion_analysis", "content_summarization", "entity_recognition"],
    "not_started_modules": ["visual_analysis", "multimodal_fusion"],
    "media_info": {
      "duration": 1800,
      "processed_duration": 1206,
      "file_name": "interview_session_12.mp4",
      "media_type": "video"
    },
    "quality_assessment": {
      "confidence": "medium",
      "completeness": "partial",
      "usability": "limited"
    }
  }
}
```

## 5. Wiederaufnahme abgebrochener Analysen

### 5.1 Wiederaufnahmestrategien

Das AIMA-System bietet verschiedene Strategien zur Wiederaufnahme abgebrochener Analysen:

```python
class AnalysisResumptionManager:
    def __init__(self, job_manager, storage_manager, checkpoint_manager):
        self.job_manager = job_manager
        self.storage_manager = storage_manager
        self.checkpoint_manager = checkpoint_manager
    
    def get_resumption_options(self, job_id):
        """Ermittelt die verfügbaren Optionen zur Wiederaufnahme eines abgebrochenen Jobs."""
        # 1. Hole Jobinformationen
        job_info = self.job_manager.get_job_info(job_id)
        if not job_info or job_info["status"] not in ["aborted", "failed", "paused_for_recovery"]:
            return {"resumable": False, "reason": "Job is not in a resumable state"}
        
        # 2. Prüfe auf Checkpoints
        checkpoints = self.checkpoint_manager.get_checkpoints(job_id)
        
        # 3. Hole Teilergebnisse
        partial_results = self.storage_manager.list_partial_results(job_id)
        
        # 4. Bestimme Wiederaufnahmeoptionen
        resumption_options = []
        
        if checkpoints:
            # Option: Vom letzten Checkpoint fortsetzen
            latest_checkpoint = max(checkpoints, key=lambda x: x["timestamp"])
            resumption_options.append({
                "type": "checkpoint",
                "checkpoint_id": latest_checkpoint["checkpoint_id"],
                "timestamp": latest_checkpoint["timestamp"],
                "completed_percentage": latest_checkpoint["metadata"]["completed_percentage"],
                "description": f"Fortsetzen vom letzten Checkpoint ({latest_checkpoint['metadata']['completed_percentage']}% abgeschlossen)"
            })
        
        if partial_results:
            # Option: Teilergebnisse verwenden und fehlende Teile neu berechnen
            latest_result = max(partial_results, key=lambda x: x["timestamp"])
            resumption_options.append({
                "type": "partial_results",
                "result_id": latest_result["result_id"],
                "timestamp": latest_result["timestamp"],
                "completed_percentage": latest_result["metadata"]["completed_percentage"] if "completed_percentage" in latest_result["metadata"] else 0,
                "description": f"Teilergebnisse verwenden und fehlende Teile neu berechnen ({latest_result['metadata'].get('completed_percentage', 0)}% verfügbar)"
            })
        
        # Option: Vollständig neu starten
        resumption_options.append({
            "type": "restart",
            "description": "Analyse vollständig neu starten"
        })
        
        return {
            "resumable": True,
            "options": resumption_options,
            "recommended_option": self._get_recommended_option(resumption_options, job_info)
        }
    
    def _get_recommended_option(self, options, job_info):
        """Bestimmt die empfohlene Wiederaufnahmeoption."""
        if not options:
            return None
        
        # Priorisiere Checkpoint > Teilergebnisse > Neustart
        for option_type in ["checkpoint", "partial_results", "restart"]:
            matching_options = [opt for opt in options if opt["type"] == option_type]
            if matching_options:
                return matching_options[0]
        
        return options[0]
    
    def resume_analysis(self, job_id, resumption_option):
        """Nimmt die Analyse mit der angegebenen Option wieder auf."""
        option_type = resumption_option["type"]
        
        if option_type == "checkpoint":
            return self._resume_from_checkpoint(job_id, resumption_option["checkpoint_id"])
        elif option_type == "partial_results":
            return self._resume_with_partial_results(job_id, resumption_option["result_id"])
        elif option_type == "restart":
            return self._restart_analysis(job_id)
        else:
            raise ValueError(f"Unknown resumption option type: {option_type}")
    
    def _resume_from_checkpoint(self, job_id, checkpoint_id):
        """Setzt die Analyse von einem Checkpoint fort."""
        # 1. Lade den Checkpoint
        checkpoint = self.checkpoint_manager.load_checkpoint(checkpoint_id)
        if not checkpoint:
            return {"success": False, "error": "Checkpoint not found"}
        
        # 2. Erstelle einen neuen Job basierend auf dem Checkpoint
        new_job_id = self.job_manager.create_job_from_checkpoint(job_id, checkpoint)
        
        # 3. Starte den neuen Job
        self.job_manager.start_job(new_job_id)
        
        return {
            "success": True,
            "original_job_id": job_id,
            "new_job_id": new_job_id,
            "resumption_type": "checkpoint",
            "checkpoint_id": checkpoint_id
        }
    
    def _resume_with_partial_results(self, job_id, result_id):
        """Setzt die Analyse mit Teilergebnissen fort."""
        # 1. Lade die Teilergebnisse
        partial_results = self.storage_manager.get_partial_results(result_id)
        if not partial_results:
            return {"success": False, "error": "Partial results not found"}
        
        # 2. Analysiere, welche Module abgeschlossen sind und welche neu ausgeführt werden müssen
        completed_modules = partial_results["metadata"].get("completed_modules", [])
        incomplete_modules = partial_results["metadata"].get("incomplete_modules", [])
        not_started_modules = partial_results["metadata"].get("not_started_modules", [])
        
        # 3. Erstelle einen neuen Job mit den Teilergebnissen als Eingabe für die fehlenden Module
        new_job_id = self.job_manager.create_job_with_partial_results(
            job_id, partial_results, completed_modules, incomplete_modules, not_started_modules
        )
        
        # 4. Starte den neuen Job
        self.job_manager.start_job(new_job_id)
        
        return {
            "success": True,
            "original_job_id": job_id,
            "new_job_id": new_job_id,
            "resumption_type": "partial_results",
            "result_id": result_id,
            "completed_modules": completed_modules,
            "modules_to_process": incomplete_modules + not_started_modules
        }
    
    def _restart_analysis(self, job_id):
        """Startet die Analyse vollständig neu."""
        # 1. Hole die ursprünglichen Jobparameter
        original_job = self.job_manager.get_job_info(job_id)
        if not original_job:
            return {"success": False, "error": "Original job not found"}
        
        # 2. Erstelle einen neuen Job mit den gleichen Parametern
        new_job_id = self.job_manager.clone_job(job_id)
        
        # 3. Starte den neuen Job
        self.job_manager.start_job(new_job_id)
        
        return {
            "success": True,
            "original_job_id": job_id,
            "new_job_id": new_job_id,
            "resumption_type": "restart"
        }
```

### 5.2 Benutzerinteraktion bei der Wiederaufnahme

Die Benutzeroberfläche bietet klare Optionen zur Wiederaufnahme abgebrochener Analysen:

```typescript
// React-Komponente für die Wiederaufnahme abgebrochener Analysen
import React, { useState, useEffect } from 'react';
import { 
  Button, Card, CardContent, Typography, RadioGroup, 
  FormControlLabel, Radio, CircularProgress, Alert 
} from '@mui/material';
import { RestartAlt, PlayArrow, Warning } from '@mui/icons-material';
import { getResumptionOptions, resumeAnalysis } from '../api/analysisService';

interface ResumptionOption {
  type: 'checkpoint' | 'partial_results' | 'restart';
  description: string;
  checkpoint_id?: string;
  result_id?: string;
  timestamp?: string;
  completed_percentage?: number;
}

interface ResumptionOptionsResponse {
  resumable: boolean;
  options?: ResumptionOption[];
  recommended_option?: ResumptionOption;
  reason?: string;
}

const AnalysisResumptionDialog: React.FC<{ jobId: string, onResume: (newJobId: string) => void, onCancel: () => void }> = ({ 
  jobId, 
  onResume, 
  onCancel 
}) => {
  const [loading, setLoading] = useState<boolean>(true);
  const [resumptionOptions, setResumptionOptions] = useState<ResumptionOptionsResponse | null>(null);
  const [selectedOption, setSelectedOption] = useState<string>('');
  const [resuming, setResuming] = useState<boolean>(false);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    const fetchOptions = async () => {
      try {
        const options = await getResumptionOptions(jobId);
        setResumptionOptions(options);
        if (options.recommended_option) {
          setSelectedOption(options.recommended_option.type);
        }
      } catch (err) {
        setError('Fehler beim Abrufen der Wiederaufnahmeoptionen');
      } finally {
        setLoading(false);
      }
    };

    fetchOptions();
  }, [jobId]);

  const handleResume = async () => {
    if (!resumptionOptions?.options) return;
    
    const option = resumptionOptions.options.find(opt => opt.type === selectedOption);
    if (!option) return;
    
    setResuming(true);
    setError('');
    
    try {
      const result = await resumeAnalysis(jobId, option);
      if (result.success) {
        onResume(result.new_job_id);
      } else {
        setError(result.error || 'Fehler bei der Wiederaufnahme der Analyse');
      }
    } catch (err) {
      setError('Fehler bei der Wiederaufnahme der Analyse');
    } finally {
      setResuming(false);
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent sx={{ textAlign: 'center', p: 4 }}>
          <CircularProgress />
          <Typography variant="body1" sx={{ mt: 2 }}>
            Wiederaufnahmeoptionen werden geladen...
          </Typography>
        </CardContent>
      </Card>
    );
  }

  if (!resumptionOptions?.resumable) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6" color="error" gutterBottom>
            <Warning color="error" sx={{ verticalAlign: 'middle', mr: 1 }} />
            Analyse kann nicht wiederaufgenommen werden
          </Typography>
          <Typography variant="body1">
            {resumptionOptions?.reason || 'Die Analyse kann aus unbekannten Gründen nicht wiederaufgenommen werden.'}
          </Typography>
          <Button 
            variant="contained" 
            color="primary" 
            onClick={onCancel} 
            sx={{ mt: 2 }}
          >
            Zurück
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Analyse wiederaufnehmen
        </Typography>
        
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        
        <Typography variant="body1" gutterBottom>
          Wählen Sie, wie die abgebrochene Analyse fortgesetzt werden soll:
        </Typography>
        
        <RadioGroup
          value={selectedOption}
          onChange={(e) => setSelectedOption(e.target.value)}
        >
          {resumptionOptions?.options?.map((option) => (
            <FormControlLabel
              key={option.type}
              value={option.type}
              control={<Radio />}
              label={
                <div>
                  <Typography variant="body1">{option.description}</Typography>
                  {option.timestamp && (
                    <Typography variant="caption" color="textSecondary">
                      Zeitpunkt: {new Date(option.timestamp).toLocaleString()}
                    </Typography>
                  )}
                  {option.completed_percentage !== undefined && (
                    <Typography variant="caption" color="textSecondary" sx={{ display: 'block' }}>
                      Fortschritt: {option.completed_percentage}%
                    </Typography>
                  )}
                </div>
              }
            />
          ))}
        </RadioGroup>
        
        <div style={{ marginTop: 20, display: 'flex', justifyContent: 'flex-end' }}>
          <Button 
            variant="outlined" 
            onClick={onCancel} 
            sx={{ mr: 1 }}
            disabled={resuming}
          >
            Abbrechen
          </Button>
          <Button 
            variant="contained" 
            color="primary" 
            onClick={handleResume}
            disabled={!selectedOption || resuming}
            startIcon={selectedOption === 'restart' ? <RestartAlt /> : <PlayArrow />}
          >
            {resuming ? 'Wird fortgesetzt...' : 'Analyse fortsetzen'}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

export default AnalysisResumptionDialog;
```

## 6. Benachrichtigungen und Benutzerinteraktion

### 6.1 Benachrichtigungstypen

Das System sendet verschiedene Arten von Benachrichtigungen bei Abbrüchen:

```python
class AbortNotificationService:
    def __init__(self, notification_manager):
        self.notification_manager = notification_manager
    
    def notify_user_about_abort(self, user_id, abort_info):
        """Benachrichtigt den Benutzer über einen Abbruch."""
        abort_type = abort_info.get("type", "unknown")
        job_id = abort_info.get("job_id")
        job_name = abort_info.get("job_name", "Unbekannte Analyse")
        
        if abort_type == "user_initiated":
            self._send_user_initiated_abort_notification(user_id, job_id, job_name, abort_info)
        elif abort_type == "system_initiated":
            self._send_system_initiated_abort_notification(user_id, job_id, job_name, abort_info)
        elif abort_type == "partial":
            self._send_partial_abort_notification(user_id, job_id, job_name, abort_info)
        else:
            self._send_generic_abort_notification(user_id, job_id, job_name, abort_info)
    
    def _send_user_initiated_abort_notification(self, user_id, job_id, job_name, abort_info):
        """Sendet eine Benachrichtigung über einen benutzerinitiiertem Abbruch."""
        partial_results = abort_info.get("partial_results", {})
        completed_percentage = partial_results.get("completed_percentage", 0) if partial_results else 0
        
        notification = {
            "type": "analysis_aborted",
            "subtype": "user_initiated",
            "priority": "medium",
            "title": f"Analyse '{job_name}' wurde abgebrochen",
            "message": f"Die Analyse wurde auf Ihre Anfrage hin abgebrochen. {completed_percentage}% der Analyse wurden abgeschlossen.",
            "actions": [
                {
                    "label": "Teilergebnisse anzeigen",
                    "action": "view_partial_results",
                    "params": {"job_id": job_id}
                },
                {
                    "label": "Analyse neu starten",
                    "action": "restart_analysis",
                    "params": {"job_id": job_id}
                }
            ],
            "metadata": {
                "job_id": job_id,
                "abort_timestamp": abort_info.get("timestamp"),
                "completed_percentage": completed_percentage
            }
        }
        
        self.notification_manager.send_notification(user_id, notification)
    
    def _send_system_initiated_abort_notification(self, user_id, job_id, job_name, abort_info):
        """Sendet eine Benachrichtigung über einen systeminitiiertem Abbruch."""
        error_info = abort_info.get("error_analysis", {})
        error_type = error_info.get("type", "unknown")
        recoverable = error_info.get("recoverable", False)
        partial_results = abort_info.get("partial_results", {})
        completed_percentage = partial_results.get("completed_percentage", 0) if partial_results else 0
        
        title = f"Analyse '{job_name}' wurde aufgrund eines Fehlers abgebrochen"
        
        if error_type == "resource_exhaustion":
            message = "Die Analyse wurde aufgrund von Ressourcenmangel abgebrochen. "
        elif error_type == "internal_error":
            message = "Die Analyse wurde aufgrund eines internen Fehlers abgebrochen. "
        elif error_type == "timeout":
            message = "Die Analyse wurde aufgrund einer Zeitüberschreitung abgebrochen. "
        else:
            message = "Die Analyse wurde aufgrund eines Systemfehlers abgebrochen. "
        
        message += f"{completed_percentage}% der Analyse wurden abgeschlossen."
        
        actions = [
            {
                "label": "Teilergebnisse anzeigen",
                "action": "view_partial_results",
                "params": {"job_id": job_id}
            }
        ]
        
        if recoverable:
            actions.append({
                "label": "Analyse fortsetzen",
                "action": "resume_analysis",
                "params": {"job_id": job_id}
            })
        else:
            actions.append({
                "label": "Analyse neu starten",
                "action": "restart_analysis",
                "params": {"job_id": job_id}
            })
        
        notification = {
            "type": "analysis_aborted",
            "subtype": "system_initiated",
            "priority": "high",
            "title": title,
            "message": message,
            "actions": actions,
            "metadata": {
                "job_id": job_id,
                "abort_timestamp": abort_info.get("timestamp"),
                "completed_percentage": completed_percentage,
                "error_type": error_type,
                "recoverable": recoverable
            }
        }
        
        self.notification_manager.send_notification(user_id, notification)
    
    def _send_partial_abort_notification(self, user_id, job_id, job_name, abort_info):
        """Sendet eine Benachrichtigung über einen Teilabbruch."""
        impact_assessment = abort_info.get("impact_assessment", {})
        failed_module = abort_info.get("failed_module", "Unbekanntes Modul")
        alternative_used = abort_info.get("alternative_used", False)
        affected_features = impact_assessment.get("affected_features", [])
        quality_impact = impact_assessment.get("quality_impact", "unknown")
        
        title = f"Analyse '{job_name}' wird mit eingeschränkter Funktionalität fortgesetzt"
        
        if alternative_used:
            message = f"Das Modul '{failed_module}' ist ausgefallen, aber ein alternatives Modul wird verwendet. "
        else:
            message = f"Das Modul '{failed_module}' ist ausgefallen und die Analyse wird mit reduzierter Funktionalität fortgesetzt. "
        
        if affected_features:
            message += f"Folgende Funktionen sind betroffen: {', '.join(affected_features)}. "
        
        if quality_impact == "low":
            message += "Die Auswirkungen auf die Ergebnisqualität sind minimal."
        elif quality_impact == "medium":
            message += "Die Ergebnisqualität könnte moderat beeinträchtigt sein."
        elif quality_impact == "high":
            message += "Die Ergebnisqualität wird erheblich beeinträchtigt sein."
        
        notification = {
            "type": "analysis_partial_abort",
            "priority": "medium",
            "title": title,
            "message": message,
            "actions": [
                {
                    "label": "Details anzeigen",
                    "action": "view_analysis_details",
                    "params": {"job_id": job_id}
                },
                {
                    "label": "Analyse abbrechen",
                    "action": "abort_analysis",
                    "params": {"job_id": job_id}
                }
            ],
            "metadata": {
                "job_id": job_id,
                "failed_module": failed_module,
                "alternative_used": alternative_used,
                "affected_features": affected_features,
                "quality_impact": quality_impact
            }
        }
        
        self.notification_manager.send_notification(user_id, notification)
    
    def _send_generic_abort_notification(self, user_id, job_id, job_name, abort_info):
        """Sendet eine generische Benachrichtigung über einen Abbruch."""
        # Implementierung der generischen Benachrichtigung
        pass
```

### 6.2 Benutzeroptionen nach Abbruch

Die Benutzeroberfläche bietet verschiedene Optionen nach einem Abbruch:

```typescript
// React-Komponente für die Anzeige von Abbruchdetails und Optionen
import React, { useState, useEffect } from 'react';
import { 
  Card, CardContent, Typography, Button, Divider, 
  Chip, Grid, Alert, CircularProgress, Box 
} from '@mui/material';
import { 
  Error as ErrorIcon, 
  Warning as WarningIcon, 
  CheckCircle as CheckCircleIcon, 
  Info as InfoIcon,
  Refresh as RefreshIcon,
  PlayArrow as PlayArrowIcon,
  Delete as DeleteIcon
} from '@mui/icons-material';
import { getAbortDetails, deleteAnalysis } from '../api/analysisService';
import AnalysisResumptionDialog from './AnalysisResumptionDialog';

interface AbortDetailsProps {
  jobId: string;
  onNavigateToResults: (jobId: string) => void;
  onNavigateToNewAnalysis: (newJobId?: string) => void;
}

const AbortDetails: React.FC<AbortDetailsProps> = ({ 
  jobId, 
  onNavigateToResults, 
  onNavigateToNewAnalysis 
}) => {
  const [loading, setLoading] = useState<boolean>(true);
  const [abortDetails, setAbortDetails] = useState<any>(null);
  const [error, setError] = useState<string>('');
  const [showResumptionDialog, setShowResumptionDialog] = useState<boolean>(false);
  const [deleting, setDeleting] = useState<boolean>(false);

  useEffect(() => {
    const fetchDetails = async () => {
      try {
        const details = await getAbortDetails(jobId);
        setAbortDetails(details);
      } catch (err) {
        setError('Fehler beim Laden der Abbruchdetails');
      } finally {
        setLoading(false);
      }
    };

    fetchDetails();
  }, [jobId]);

  const handleDelete = async () => {
    if (!window.confirm('Möchten Sie diese Analyse wirklich löschen? Alle Teilergebnisse gehen verloren.')) {
      return;
    }
    
    setDeleting(true);
    try {
      await deleteAnalysis(jobId);
      onNavigateToNewAnalysis();
    } catch (err) {
      setError('Fehler beim Löschen der Analyse');
      setDeleting(false);
    }
  };

  const handleResume = (newJobId: string) => {
    setShowResumptionDialog(false);
    onNavigateToNewAnalysis(newJobId);
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error">{error}</Alert>
    );
  }

  if (!abortDetails) {
    return (
      <Alert severity="warning">Keine Abbruchdetails verfügbar</Alert>
    );
  }

  const {
    abort_type,
    timestamp,
    partial_results,
    error_info,
    job_name
  } = abortDetails;

  return (
    <>
      {showResumptionDialog ? (
        <AnalysisResumptionDialog 
          jobId={jobId} 
          onResume={handleResume} 
          onCancel={() => setShowResumptionDialog(false)} 
        />
      ) : (
        <Card>
          <CardContent>
            <Typography variant="h5" gutterBottom>
              Analyse abgebrochen
            </Typography>
            
            <Divider sx={{ my: 2 }} />
            
            <Grid container spacing={2}>
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle1" gutterBottom>
                  Analysename
                </Typography>
                <Typography variant="body1">
                  {job_name}
                </Typography>
              </Grid>
              
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle1" gutterBottom>
                  Abbruchzeitpunkt
                </Typography>
                <Typography variant="body1">
                  {new Date(timestamp).toLocaleString()}
                </Typography>
              </Grid>
              
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle1" gutterBottom>
                  Abbruchtyp
                </Typography>
                <Chip 
                  icon={abort_type === 'user_initiated' ? <InfoIcon /> : <WarningIcon />} 
                  label={abort_type === 'user_initiated' ? 'Benutzerabbruch' : 'Systemabbruch'} 
                  color={abort_type === 'user_initiated' ? 'primary' : 'error'} 
                  size="small" 
                />
              </Grid>
              
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle1" gutterBottom>
                  Fortschritt bei Abbruch
                </Typography>
                <Typography variant="body1">
                  {partial_results?.completed_percentage || 0}%
                </Typography>
              </Grid>
              
              {error_info && (
                <Grid item xs={12}>
                  <Alert severity="error" sx={{ mt: 2 }}>
                    <Typography variant="subtitle1">
                      Fehlerdetails:
                    </Typography>
                    <Typography variant="body2">
                      {error_info.message}
                    </Typography>
                  </Alert>
                </Grid>
              )}
            </Grid>
            
            <Divider sx={{ my: 2 }} />
            
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 2 }}>
              <div>
                {partial_results && partial_results.available && (
                  <Button 
                    variant="outlined" 
                    onClick={() => onNavigateToResults(jobId)}
                    startIcon={<CheckCircleIcon />}
                    sx={{ mr: 1 }}
                  >
                    Teilergebnisse anzeigen
                  </Button>
                )}
              </div>
              
              <div>
                <Button 
                  variant="outlined" 
                  color="error" 
                  onClick={handleDelete}
                  startIcon={<DeleteIcon />}
                  disabled={deleting}
                  sx={{ mr: 1 }}
                >
                  {deleting ? 'Wird gelöscht...' : 'Analyse löschen'}
                </Button>
                
                <Button 
                  variant="outlined" 
                  color="primary" 
                  onClick={() => onNavigateToNewAnalysis()}
                  startIcon={<RefreshIcon />}
                  sx={{ mr: 1 }}
                >
                  Neue Analyse starten
                </Button>
                
                <Button 
                  variant="contained" 
                  color="primary" 
                  onClick={() => setShowResumptionDialog(true)}
                  startIcon={<PlayArrowIcon />}
                >
                  Analyse fortsetzen
                </Button>
              </div>
            </Box>
          </CardContent>
        </Card>
      )}
    </>
  );
};

export default AbortDetails;
```

## 7. Implementierungsplan

### 7.1 Phasen der Implementierung

Die Implementierung des Abbruchverhaltens und Teilergebnismanagements erfolgt in drei Phasen:

#### Phase 1: Grundlegende Abbruchbehandlung (Monat 1-2)

- Implementierung der grundlegenden Abbrucherkennung und -signalisierung
- Entwicklung der Basisklassen für `UserInitiatedAbortHandler` und `SystemInitiatedAbortHandler`
- Einfache Speicherung von Teilergebnissen ohne komplexe Strukturierung
- Grundlegende Benutzerbenachrichtigungen bei Abbrüchen

#### Phase 2: Erweitertes Teilergebnismanagement (Monat 3-4)

- Vollständige Implementierung des `PartialResultsManager` mit strukturierter Speicherung
- Entwicklung des `PartialAbortHandler` für Teilabbrüche
- Implementierung der Wiederaufnahmelogik mit Checkpoints
- Erweiterte Benutzeroberfläche für Abbruchdetails und Wiederaufnahmeoptionen

#### Phase 3: Optimierung und Integration (Monat 5-6)

- Optimierung der Teilergebnisspeicherung für große Datenmengen
- Integration mit dem Monitoring- und Alerting-System
- Verbesserung der Fehleranalyse und automatischen Wiederaufnahmeentscheidungen
- Umfassende Tests mit verschiedenen Abbruchszenarien
- Dokumentation und Schulung der Benutzer

### 7.2 Abhängigkeiten und Voraussetzungen

Für die erfolgreiche Implementierung des Abbruchverhaltens sind folgende Komponenten erforderlich:

- Funktionierendes Job-Management-System
- Zuverlässiges Speichersystem für Teilergebnisse (Datenbank und Objektspeicher)
- Benachrichtigungssystem für Benutzerbenachrichtigungen
- Monitoring-System zur Erkennung von Systemfehlern
- Checkpoint-Mechanismus für die Wiederaufnahme von Analysen

### 7.3 Testplan

Das Abbruchverhalten wird mit folgenden Testszenarien validiert:

1. **Benutzerabbruch-Tests**:
   - Abbruch in verschiedenen Phasen der Analyse (früh, mittel, spät)
   - Abbruch während ressourcenintensiver Operationen
   - Abbruch bei verschiedenen Medientypen und -größen

2. **Systemabbruch-Tests**:
   - Simulation von Ressourcenengpässen (Speicher, CPU, GPU)
   - Simulation von Netzwerkunterbrechungen
   - Simulation von Komponentenausfällen
   - Zeitüberschreitungen bei langläufigen Prozessen

3. **Teilergebnis-Tests**:
   - Korrektheit und Vollständigkeit der gespeicherten Teilergebnisse
   - Leistung bei großen Datenmengen
   - Datenkonsistenz bei abrupten Abbrüchen

4. **Wiederaufnahme-Tests**:
   - Wiederaufnahme von verschiedenen Checkpoints
   - Wiederaufnahme mit Teilergebnissen
   - Wiederaufnahme nach verschiedenen Fehlertypen

## 8. Zusammenfassung

Das Abbruchverhalten und Teilergebnismanagement des AIMA-Systems ist darauf ausgelegt, in allen Abbruchszenarien maximale Datensicherheit und Benutzerfreundlichkeit zu gewährleisten. Durch die klare Unterscheidung zwischen benutzer- und systeminitiiertem Abbruch sowie die Behandlung von Teilabbrüchen wird eine differenzierte und angemessene Reaktion auf verschiedene Situationen ermöglicht.

Die strukturierte Speicherung von Teilergebnissen mit umfangreichen Metadaten erlaubt eine effiziente Wiederverwendung bereits berechneter Daten und minimiert den Verlust von Arbeitszeit und Ressourcen. Die verschiedenen Wiederaufnahmeoptionen geben Benutzern die Flexibilität, je nach Situation die optimale Strategie zu wählen.

Durch die transparente Kommunikation des Abbruchstatus und der verfügbaren Optionen wird eine positive Benutzererfahrung auch in Fehlersituationen sichergestellt. Die Integration mit dem Benachrichtigungssystem ermöglicht eine zeitnahe Information der Benutzer über den Status ihrer Analysen.

Insgesamt trägt das hier spezifizierte Abbruchverhalten wesentlich zur Robustheit, Effizienz und Benutzerfreundlichkeit des AIMA-Systems bei und stellt sicher, dass auch in unvorhergesehenen Situationen ein Maximum an Wert aus den durchgeführten Analysen gezogen werden kann.