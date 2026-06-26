# Grok — THERMAL-001-R1
Дата: 2026-06-23 10:43:47.167502

Q-КОД-1: Как определены и переходят 9 состояний FSM в ThermalGuard v9.4?
Q-КОД-2: Где именно в коде возникает race condition, вызывающая 2 FAIL в self-test?
Q-КОД-3: Как ThermalGuard запускает powermetrics без sudo и почему powermetrics_available мигает?
Q-КОД-4: Какие точные критерии перехода state=DEGRADED → HEALTHY?
Q-КОД-5: Почему ollama_available=false при ollama_serve_up=true?
Q-КОД-6: Как ThrottleInterval=30 влияет на цикл launchd агента?

Q-АРХ-1: Какое место ThermalGuard занимает в системе NEVA?
Q-АРХ-2: Как будет реализован kill-action при CRITICAL?
Q-АРХ-3: Как должен работать полный UDS-канал ThermalGuard ↔ Medic?
Q-АРХ-4: Кто кем управляет: ThermalGuard Medic'ом или наоборот?
Q-АРХ-5: Как планируется расширяемость ThermalGuard на Этапе 2?