# Geschätzte Betriebskosten für AIMA auf AWS

Dieses Dokument bietet eine grobe Schätzung der monatlichen Kosten für den Betrieb der AIMA-Plattform auf Amazon Web Services (AWS). Die tatsächlichen Kosten können je nach Nutzung, Region und gewählten Konfigurationen stark variieren.

Die Architektur basiert auf den Komponenten, die in der `TECHNISCHE_BLAUPAUSE.md` definiert sind.

## 1. Kostenübersicht nach Komponenten

Die Gesamtkosten setzen sich aus den folgenden Hauptkomponenten zusammen:

### 1.1. Kubernetes Cluster (Amazon EKS)

- **EKS Control Plane**: Fixkosten pro Cluster.
  - *Schätzung*: ca. **$73/Monat**.
- **Worker Nodes (EC2-Instanzen)**: Dies sind die Server, auf denen die Anwendungscontainer laufen. Die Kosten hängen von Instanztyp und Anzahl ab.
  - **Für System-Services (ohne GPU)**: z.B. 2x `t3.medium` Instanzen für API-Gateway, Backend-Services, etc.
    - *Schätzung*: 2 * ~$30/Monat = **$60/Monat**.

### 1.2. GPU-Instanzen (EC2)

Dies ist der **größte und variabelste Kostenfaktor**. Die Kosten hängen direkt von der Anzahl der Analysejobs und dem gewählten GPU-Typ ab. AIMA ist darauf ausgelegt, GPU-Instanzen dynamisch (auch Spot-Instanzen) zu nutzen, um Kosten zu sparen.

- **Beispielrechnung (On-Demand)**:
  - Eine `g4dn.xlarge` (NVIDIA T4 GPU) kostet ca. $0.526/Stunde.
  - Bei einer Nutzung von 100 Stunden pro Monat: 100 * $0.526 = **$52.60/Monat**.
  - Bei einer Nutzung von 500 Stunden pro Monat: 500 * $0.526 = **$263/Monat**.
- **Spot-Instanzen**: Können die Kosten um 50-70% senken, sind aber nicht immer verfügbar. Der GPU-Orchestrator von AIMA ist darauf ausgelegt, diese zu nutzen.

### 1.3. Speicher (Amazon S3)

Kosten für die Speicherung von Medien-Assets (Videos, Bilder, Audios).

- **S3 Standard Storage**: Kosten pro GB pro Monat.
  - *Schätzung (bei 1 TB Speicher)*: ca. **$23/Monat**.
- **Datenübertragung**: Kosten für das Hoch- und Herunterladen von Daten.
  - Eingehender Traffic ist meist kostenlos.
  - Ausgehender Traffic (z.B. zu Endnutzern) wird pro GB abgerechnet.
  - *Schätzung (bei 100 GB ausgehend)*: ca. **$9/Monat**.

### 1.4. Managed Databases

Nutzung von AWS-Diensten für Datenbanken ist oft einfacher im Betrieb, aber teurer als selbst gehostete Alternativen.

- **PostgreSQL (Amazon RDS)**: Für strukturierte Daten.
  - *Schätzung (kleine `db.t3.micro` Instanz)*: ca. **$15/Monat**.
- **MongoDB (Amazon DocumentDB)**: Für unstrukturierte Metadaten.
  - DocumentDB ist relativ teuer. Eine kleine Instanz startet bei ca. **$200/Monat**.
  - *Alternative*: MongoDB auf einer EC2-Instanz selbst hosten (deutlich günstiger, aber mehr Verwaltungsaufwand).
- **Vektordatenbank (z.B. Pinecone/Milvus)**:
  - **Pinecone**: Als externer SaaS-Dienst. Kosten starten bei ca. **$70/Monat** für einen kleinen Index.
  - **Milvus**: Kann auf dem EKS-Cluster selbst gehostet werden. Verursacht dann Kosten durch die genutzten EC2-Ressourcen (CPU/RAM).

### 1.5. Nachrichtensystem (z.B. Amazon MQ)

Für die asynchrone Kommunikation zwischen den Microservices.

- **Amazon MQ (für RabbitMQ)**: 
  - *Schätzung (kleine Instanz)*: ca. **$20/Monat**.

### 1.6. API Gateway & Netzwerk

- **AWS API Gateway**: Kosten pro Million Anfragen + Datenübertragung.
  - *Schätzung (1 Million Anfragen)*: ca. **$1/Monat**.
- **Alternative (Traefik/Kong)**: Läuft auf dem EKS-Cluster und verursacht keine direkten Zusatzkosten außer den EC2-Ressourcen.

## 2. Szenario-basierte Kostenschätzungen (Monatlich)

### Szenario 1: Entwicklung / Kleiner Prototyp

- **Annahmen**: Geringe Last, nur wenige Analysen, Nutzung von günstigen Instanzen und Spot-GPUs.
- **EKS**: $73 (Control Plane) + $60 (Worker) = $133
- **GPU**: 50 Spot-Stunden ~ $15
- **S3**: 100 GB Speicher ~ $3
- **Datenbanken**: RDS ($15) + MongoDB auf EC2 ($15) + Milvus auf EKS (vernachlässigbar) = $30
- **Sonstiges**: $20 (MQ etc.)
- **Geschätzte Gesamtkosten**: **~ $200 - $300 / Monat**

### Szenario 2: Produktivbetrieb (Mittel)

- **Annahmen**: Regelmäßige Nutzung, mehrere parallele Analysen, größere Datenmengen.
- **EKS**: $73 (Control Plane) + $120 (größere Worker) = $193
- **GPU**: 500 On-Demand-Stunden ~ $260
- **S3**: 1 TB Speicher + Transfer ~ $35
- **Datenbanken**: RDS ($30) + DocumentDB ($200) + Pinecone ($70) = $300
- **Sonstiges**: $40 (MQ etc.)
- **Geschätzte Gesamtkosten**: **~ $800 - $1.200 / Monat**

### Szenario 3: Großer Produktivbetrieb (Skaliert)

- **Annahmen**: Hohe Last, kontinuierliche Analysen, große und redundante Infrastruktur.
- **EKS**: $73 (Control Plane) + $500+ (viele/große Worker) = $573+
- **GPU**: Mehrere tausend Stunden, Mix aus On-Demand/Spot ~ **$1.500 - $5.000+**
- **S3**: 10+ TB Speicher + viel Transfer ~ $250+
- **Datenbanken**: Größere, redundante Instanzen ~ $800+
- **Sonstiges**: $100+
- **Geschätzte Gesamtkosten**: **$3.000 - $10.000+ / Monat**

## 3. Fazit

Die Betriebskosten für AIMA sind stark von der **GPU-Nutzung** und der Wahl zwischen **Managed Services vs. Self-Hosting** abhängig. Für einen Start und die Entwicklung ist ein Betrieb mit einigen hundert Euro pro Monat realistisch. Ein produktiver, skalierbarer Betrieb erfordert jedoch ein signifikantes Budget, das in die Tausende gehen kann.

Eine kontinuierliche Kostenüberwachung und -optimierung, insbesondere durch die intelligente Nutzung von Spot-GPU-Instanzen durch den AIMA-Orchestrator, ist entscheidend für die Wirtschaftlichkeit des Systems.