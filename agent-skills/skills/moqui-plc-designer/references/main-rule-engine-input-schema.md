# MainRuleEngine Input Schema

Questo schema definisce i dati minimi necessari per generare:

- `${SENSOR_PREDICATES}`
- `${STATE_TRANSITION_CASES}`

nel template:

- `references/plc-codegen-templates/MainRuleEngine.template.pou`

## Obiettivo

Separare chiaramente:

- topologia della FSM, derivabile da `StatusFlow`
- semantica dei predicati, da fornire o confermare
- precedenza delle transizioni

## Struttura

Lo schema YAML di esempio e' in:

- [main-rule-engine-input-schema.yaml](./main-rule-engine-input-schema.yaml)

## Sezioni principali

### `context`

Informazioni generali:

- `component_name`
- `status_enum`
- `main_status_flow_id`
- `initial_state`

### `request_reset_block`

Elenca quali request vanno resettate all'inizio di ogni scan.

### `predicate_groups`

Raggruppa i predicati per dominio:

- `process`
- `environment`
- `safety`
- `timing`
- `custom`

Ogni predicato ha:

- `name`
- `target`
- `expression`
- `comment`
- `depends_on`

### `transitions`

Una voce per ogni arco di `StatusFlowTransition`.

Campi principali:

- `from_status`
- `to_status`
- `transition_name`
- `priority`
- `condition`
- `request_assignments`
- `comment`

### `global_fault_gate`

Specifica eventuali condizioni globali che causano `faultRequest`.

## Regole di generazione

- `${SENSOR_PREDICATES}` si genera concatenando i `predicate_groups`
- `${STATE_TRANSITION_CASES}` si genera raggruppando le `transitions` per `from_status`
- l'ordine degli `ELSIF` deriva da `priority`
- se manca `condition`, lo skill deve chiedere chiarimenti all'utente
- lo skill puo' precompilare parti dello schema leggendo:
  - seed XML `StatusFlowItem`
  - seed XML `StatusFlowTransition`
  - seed XML `ParameterDef`
  - seed XML `Parameter`
  - seed XML `DeviceRequestItem`
