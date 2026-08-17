# Offline analysis boundary

Offline analysis is a separate plane defined by ADR-0001. Stage 3 deliberately
contains no analysis implementation. Future tools in this directory may consume
immutable, validated artifacts only; they must never run in the timed process or
control the scientific measurement loop.
