# Moqui Seed XML Workflow

Questa reference descrive il workflow consigliato per creare o aggiornare dati Moqui coerenti con gli skill PLC.

## Principio

Quando il workflow deve creare o modificare dati applicativi, preferire:

- file seed XML Moqui `entity-facade-xml`

invece di:

- scritture dirette nel database

## Entita' tipiche coinvolte

- `moqui.math.ParameterDef`
- `moqui.math.Parameter`
- `moqui.device.DeviceRequest`
- `moqui.device.DeviceRequestItem`
- `moqui.basic.StatusType`
- `moqui.basic.StatusItem`
- `moqui.basic.StatusFlow`
- `moqui.basic.StatusFlowItem`
- `moqui.basic.StatusFlowTransition`

## File template

Vedi:

- [moqui-seed-template.xml](./moqui-seed-template.xml)

## Regole

### ParameterDef

Usare `ParameterDef` per definire:

- nome logico
- tipo dato
- `purposeEnumId`
- unita' di misura o semantica

Per i feedback:

- usare `purposeEnumId="PpFeedback"` quando appropriato

Per i parametri di recipe/configurazione:

- usare `purposeEnumId="PpDeviceConfiguration"` quando appropriato

### Parameter

Usare `Parameter` per associare il `ParameterDef` a:

- `deviceId`
- valore iniziale o corrente
- eventuali metadata del contesto macchina

### DeviceRequest / DeviceRequestItem

Usare questi record per:

- costruire `IOFacade`
- definire input/output logici e fisici
- separare richieste per protocollo, frequenza o funzione

### StatusFlow

Usare `StatusFlow*` per:

- derivare `MainStatus`
- derivare la topologia del `MainRuleEngine`

## Workflow consigliato

1. leggere i seed XML esistenti e i model XML
2. generare o aggiornare i file PLC template
3. generare seed XML Moqui per nuovi `ParameterDef`, `Parameter`, `DeviceRequest`, `StatusFlow`
4. validare il seed XML con naming e purpose coerenti
