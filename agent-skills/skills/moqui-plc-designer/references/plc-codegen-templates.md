# PLC Codegen Templates

Questi template sono pensati come base concreta per un futuro skill di generazione codice PLC data-driven.

Scelte già fissate in questa fase:

- `IOFacade` e' generabile automaticamente
- `DeviceFacade` e' generabile automaticamente per i tipi atomici moqui-plc supportati
- `DeviceManager` e' generabile automaticamente per i tipi atomici moqui-plc supportati, con chiamata a firma completa a ogni scan
- `DeviceDiagnostics` e' generabile automaticamente come primo scaffold per i device bloccanti supportati
- `InputSignalUpdate` e `OutputSignalUpdate` restano fuori dalla generazione automatica V1
- il mapping tra segnali fisici e logici resta manuale, a cura del field engineer / programmatore PLC
- `DeviceManager` e `DeviceDiagnostics` sono generabili automaticamente solo per macchine in cui il guasto di ogni device è bloccante
- configurazioni complesse con `DeviceGroup` / `DeviceGroupMember`, ridondanza, backup, standby e ruoli differenziati restano fuori dalla V1
- `Main` e `MainRuleEngine` restano volutamente in standby fino all'analisi di casi di test reali da cui estrarre le regole finali di generazione
- il repository va considerato come semilavorato/base framework da specializzare nei singoli team di sviluppo

Template aggiunti:

- [MainStatus.template.dut](./plc-codegen-templates/MainStatus.template.dut)
- [IOFacade.template.dut](./plc-codegen-templates/IOFacade.template.dut)
- [DeviceFacade.template.dut](./plc-codegen-templates/DeviceFacade.template.dut)
- [DeviceManager.template.pou](./plc-codegen-templates/DeviceManager.template.pou)
- [DeviceDiagnostics.template.pou](./plc-codegen-templates/DeviceDiagnostics.template.pou)
- [Main.template.pou](./plc-codegen-templates/Main.template.pou)
- [MainRuleEngine.template.pou](./plc-codegen-templates/MainRuleEngine.template.pou)

## Struttura di output consigliata

I file generati non dovrebbero finire in una directory piatta temporanea, ma in una gerarchia analoga a `mantle-hvac` in [moqui/moqui-plc](https://github.com/moqui/moqui-plc).

Layout consigliato:

- `output/<component-name>/data/`
- `output/<component-name>/src/main/<namespace>/<component-name>/`
  - `MainStatus.dut`
  - `Main.pou`
  - `MainRuleEngine.pou`
- `output/<component-name>/src/main/org/moqui/device/`
  - `IOFacade.dut`
  - `DeviceFacade.dut`
  - `DeviceManager.pou`
  - `DeviceDiagnostics.pou`

I file manuali restano fuori dalla generazione V1:

- `InputSignalUpdate.pou`
- `OutputSignalUpdate.pou`

## Placeholder principali

- `${COMPONENT_NAME}`: nome del componente/macchina, per esempio `hvac`
- `${MAIN_STATUS_ENUM}`: enum degli stati della FSM principale, per esempio `MainStatus`
- `${MAIN_STATUS_ITEMS}`: elenco ordinato degli stati dell'enum `MainStatus`
- `${PHYSICAL_INPUT_DECLARATIONS}`: elenco segnali/terminali fisici di input
- `${PHYSICAL_OUTPUT_DECLARATIONS}`: elenco segnali/terminali fisici di output
- `${ANALOG_SIGNAL_DECLARATIONS}`: elenco variabili `REAL`
- `${DIGITAL_SIGNAL_DECLARATIONS}`: elenco variabili `BOOL`
- `${ATOMIC_DEVICE_DECLARATIONS}`: istanze `Actuator`, `Axis`, `ProcessPid`, ecc.
- `${MAIN_FSM_CASE_BLOCKS}`: rami `CASE` della FSM in `Main`, uno per stato, comprensivi di output function e state-update function
- `${STATE_TRANSITION_CASES}`: rami `CASE` della rule engine, derivati dalla topologia di `StatusFlowTransition` piu' condizioni e precedenze fornite dall'utente durante il workflow o trovate nei dati esistenti
- `${SENSOR_PREDICATES}`: predicati di processo/ambiente/sicurezza derivati da parametri logici, soglie, isteresi, tempi e regole di safety
- `${BLOCKING_DEVICE_SIGNAL_RULES}`: regole diagnostiche per ogni device bloccante

Nota importante:

- convenzione standard: il nome dello stato determina il nome del request field
- esempio: `Standstill -> standstillRequest`, `Run -> runRequest`, `ErrorStop -> errorStopRequest`
- la mappa opzionale `status -> request field` resta disponibile solo come override per casi eccezionali

## Domande che guideranno lo skill

Per compilare questi template, lo skill dovrà porre domande strutturate all’utente.

### IOFacade

- Vuoi generare i nomi fisici a partire da `DeviceRequestItem.requestItemName` oppure con convenzione standard?
- Quali segnali fisici sono input?
- Quali segnali fisici sono output?
- Per ciascun segnale fisico, qual e' il tipo IEC: `BOOL`, `WORD`, `DWORD`, `REAL`, `ARRAY[..] OF WORD`, ecc.?
- Quali segnali hanno naming semantico e quali naming per indirizzo fisico?

### DeviceFacade

- Quali sono i parametri analogici di input?
- Quali sono i setpoint e i limiti analogici?
- Quali sono i parametri digitali e i flag booleani?
- Quali dispositivi di tipo `Actuator` esistono?
- Quali dispositivi di tipo `ActuatorGroup` esistono?
- Quali dispositivi di tipo `Axis` esistono?
- Quali dispositivi di tipo `AxisGroup` esistono?
- Quali dispositivi di tipo `ProcessPid` esistono?
- Quali dispositivi di tipo `SignalMgmt` esistono?
- Se presenti, quali `Device.deviceTypeEnumId` usano gia' i tipi virtuali moqui-plc:
  - `DtMoquiPlcActuator`
  - `DtMoquiPlcActuatorGroup`
  - `DtMoquiPlcProcessPID`
  - `DtMoquiPlcAxis`
  - `DtMoquiPlcAxisGroup`
  - `DtMoquiPlcSignalMgmt`

### DeviceManager

- Quali dispositivi atomici devono essere chiamati a ogni scan?
- Per ciascun tipo FB, qual e' la firma completa da rispettare?
- La chiamata deve essere emessa con tutti i parametri dichiarati nella firma, anche se alcuni valori vengono semplicemente ribaditi a ogni scan.
- Per `Axis` e `AxisGroup`, riferimenti come `master`, `slave`, `group`, `triggerInput`, `positionProfile`, `velocityProfile` e strutture robotiche appartengono al device tree CODESYS.
- Il generatore puo' emettere placeholder coerenti nel codice PLC; eventuali errori di compilazione iniziali in CODESYS sono accettabili finche' l'utente non completa il binding.

### Main

- Da quale `StatusFlow` derivano i rami del `CASE dev.status OF`?
- Quale `StatusFlow` genera `MainStatus`?
- Per ogni stato, quali output request devono essere poste a `TRUE/FALSE`?
- Per ogni stato, quali transition request possono essere consumate e a quale next state portano?
- Quali sottosistemi o device devono essere abilitati in ciascuno stato?
- Quali request flag devono essere posti a `TRUE/FALSE` in ciascuno stato?
- Queste informazioni vanno raccolte con un survey guidato stato per stato.
- Esempio:
  - partiamo da `MainStatus.Standby`
  - quali `PhysicalDevice` o `DeviceGroup` si devono attivare?
  - quali si devono disattivare?
  - quali predicati gia' definiti consentono la transizione fuori dallo stato?

### MainRuleEngine

- Quali sono i predicati di processo/ambiente/sicurezza?
- Quali predicati vanno calcolati a ogni scan?
- Per ogni transizione `StatusFlowTransition`, quali sono le condizioni di attivazione?
- Esistono override globali di fault, inhibit, emergency o safety?
- Anche queste informazioni vanno raccolte con un survey guidato transizione per transizione.

### DeviceDiagnostics

- Quali device sono bloccanti per la macchina?
- Quale condizione di fault o invalid config va monitorata per ciascuno?
- Quali segnali ambientali o di safety vanno trattati come `ImmediateStop`?
- Esistono warning non bloccanti?
