# Rust gateway port clarification — 2026-10-16

The current review uses MR-Moqui master plus moqui-device/moqui-math/gateway
branches mr-moqui. Rust gateway and Java Quarkus/Camel are independent edge
implementations of the shared model. The gateway is independent of the PLC
compiler: RuSTy/IronPLC only open experiments with simple ST programs today.
README and startup skill now distinguish the implementations.

Protocol/service regressions are tested on a separate disposable database.
These checks do not close the historical CODESYS/FAT/SAT checkpoints or authorize
resuming the old HVAC commissioning task. See the current gateway README and
tests rather than copying historical secret-bearing transport workarounds.
