# DeepSeek — THERMAL-001-R2
Дата: 2026-06-23 11:10:14.382654

АУДИТ THERMALGUARD NEVA — КРУГ 2
ПРОБЛЕМА А: powermetrics требует sudo → система навсегда в DEGRADED
🔴 КРИТИКА

Что конкретно плохо:

Полная зависимость от привилегий — powermetrics без sudo возвращает только заголовок и завершается с PermissionError. Это делает систему мертворождённой на пользовательском агента.

Отсутствие fallback-механизма — перехват ошибки логируется в thermal.log, но temp=None → _determine_level() → DEGRADED → единственный выход через BLOCKED→UNBLOCKING→NOMINAL, но без температуры туда не попасть. Система заперта навсегда.

Ложное чувство безопасности — logger.error() создаёт иллюзию, что проблема зафиксирована, но система продолжает работать в деградированном режиме без возможности восстановления.

Проектное решение "безопасное поведение" — на самом деле это безопасное, но бесполезное поведение. ThermalGuard превращается в watchdog, который всегда лает, но никогда не кусает.

✅ ЛУЧШЕЕ РЕШЕНИЕ

Гибридный сенсор: NSProcessInfo (PyObjC) + powermetrics с fallback + SMC-сенсоры через IOKit

python
Copy
Download
# thermal_sensor.py
import subprocess
import json
import logging
from typing import Optional, Tuple
from dataclasses import dataclass

@dataclass
class ThermalReading:
    temperature: Optional[float]
    pressure_level: Optional[str]  # Nominal, Light, Moderate, Severe, Critical
    source: str  # 'nsprocessinfo', 'powermetrics', 'smc', 'fallback'

class ThermalSensor:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._has_pyobjc = False
        self._init_pyobjc()
        
    def _init_pyobjc(self):
        """Инициализация PyObjC для NSProcessInfo"""
        try:
            from Foundation import NSProcessInfo
            self._ns_process_info = NSProcessInfo
            self._has_pyobjc = True
        except ImportError:
            self.logger.warning("PyObjC не доступен, устанавливается через: pip install pyobjc-framework-Foundation")
            self._has_pyobjc = False
    
    def get_thermal_state(self) -> ThermalReading:
        """Получить тепловой статус с приоритетом: powermetrics → NSProcessInfo → IOKit → fallback"""
        
        # 1. Пробуем powermetrics (если есть права)
        reading = self._try_powermetrics()
        if reading and reading.temperature is not None:
            return reading
        
        # 2. Fallback на NSProcessInfo (PyObjC)
        if self._has_pyobjc:
            reading = self._try