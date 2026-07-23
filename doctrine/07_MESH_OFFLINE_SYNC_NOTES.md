# MESH / OFFLINE SYNC — DESIGN NOTES
*Extracted from conversation #528 "Tamagotchi Code Syncing Explained" (2025-02-07) — Pre Atlas harvest pipeline, verdict MINE, decided 2026-04-21*

---

## Why this doc exists

A 591-message thread (`services/cognitive-sensor/harvest/528_tamagotchi-code-syncing-explained/`) that starts from "how did my old Tamagotchi sync without internet access" and turns into a real comparison of offline/mesh communication patterns — relevant to any future Atlas offline layer (a device that needs to sync state without a live connection, similar to the original Tamagotchi passcode problem). 2 real Python blocks out of 75; the value here is the comparison table and the design implications drawn from it, not executable code. This doc preserves that table + implication so the source conversation can be retired.

## The comparison

| System | Key tech | Offline / Online | Range | Security | Purpose |
|---|---|---|---|---|---|
| **Tamagotchi Passcodes** | Manual passcode entry | Fully offline (codes typed in manually) | N/A (no radio) | Simple proprietary encoding | Exchange items/bonuses between devices with zero connectivity |
| **PictoChat (Nintendo DS)** | Local ad-hoc Wi-Fi | Offline (device-to-device only) | Tens of meters | Minimal/none | Real-time local chat, no internet needed |
| **Apple Find My** | BLE beacons + iCloud relay | Hybrid — lost device offline, helper devices need internet | ~10-50m BLE, then global via crowd relay | End-to-end encrypted | Locate a device that has no connectivity of its own |
| **AirTag** | Low-power BLE (+ UWB) | Offline for the tag itself; piggybacks on any nearby Apple device's internet | BLE to nearest iPhone, then global | End-to-end encrypted | Same pattern as Find My, applied to passive objects |
| **MeshTastic** | LoRa radios, true mesh | Fully off-grid possible | Multiple km per hop | AES, configurable | Off-grid texting/location with zero infrastructure |

## Design implication

The common thread across all five: **the "offline" device never syncs directly** — it either (a) encodes its state into something a human manually re-enters elsewhere (Tamagotchi passcodes), or (b) piggybacks its sync onto *any* nearby device with connectivity, without needing that device to be its owner's (Find My / AirTag's crowd-relay model). A mesh-style design (MeshTastic) trades that opportunistic relay for guaranteed multi-hop coverage at the cost of needing dedicated radio hardware.

For an Atlas offline layer, the practical takeaway is the **Find My / AirTag pattern**, not the mesh-radio pattern: state changes made offline get encoded compactly (a "passcode" in Tamagotchi's own terms) and opportunistically relayed through whatever connectivity becomes available next, rather than requiring a purpose-built mesh network. This is cheaper to build and matches how Atlas devices already behave (local-first state, sync-when-online), so no new infrastructure is implied — just: when designing an offline-capable Atlas surface, prefer "encode state, relay opportunistically" over "assume a dedicated sync channel."

## Disposition

This document is the artifact. No mesh/offline infrastructure currently exists in Atlas to wire this into — the disposition is design reference for whenever an offline-capable surface is actually built, not an immediate build target. No further extraction needed from `harvest/528_tamagotchi-code-syncing-explained/`.
