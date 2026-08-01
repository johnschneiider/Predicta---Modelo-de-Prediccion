# Setup Completo Bot Predicta + Betfair

## Estado Actual

Progreso completado:

### ✅ PASO 1 - CERTIFICADOS SSL BETFAIR
- [x] Directorio `/etc/betfair/certs/` creado
- [x] Certificados SSL generados:
  - `client-2048.key` (clave privada RSA-2048)
  - `client-2048.crt` (certificado público)
  - `client-2048.pem` (combinado, para Python)
- [x] Permisos seguros (600 para claves privadas)
- [x] Settings actualizados con rutas de certificados
- [x] Servicio Betfair actualizado para manejar sandbox vs producción

### ✅ PASO 2 - PREDICTOR 1X2
- [x] `betting/predictors.py` creado
- [x] Llama modelos existentes como caja negra
- [x] Deriva probabilidades 1X2 vía Poisson usando goles esperados
- [x] CERO cambios en archivos de `ai_predictions/`

### ✅ PASO 3 - ORQUESTADOR PRINCIPAL
- [x] `betting_bot/main.py` creado
- [x] Flujo completo: Obtener partidos → Predicción → Betfair → Valor → Apuesta
- [x] Manejo de edge calculation (valor)
- [x] Kelly Criterion simplificado para stake
- [x] Logging para monitoreo

### ✅ PASO 4 - COMANDO DJANGO + SYSTEMD READY
- [x] Management command: `python manage.py run_bot`
- [x] Configuración de intervalos y ciclos
- [x] Modo dry-run para pruebas

## Próximos Pasos - DEPENDEN DEL USUARIO

### 🔄 PASO 5 - CREDENCIALES BETFAIR
**Usuario debe realizar:**
1. Crear cuenta Betfair Exchange Developer: https://developer.betfair.com/
2. Generar Application Key: Dashboard → My Account → Application Keys
3. Subir certificado público a Betfair:
   ```
   https://myaccount.betfair.com/accountdetails/mysecurity?showAPI=1
   ```
   - Buscar "Automated Betting Program Access"
   - Click 'Edit' → 'Browse'
   - Seleccionar `/etc/betfair/certs/client-2048.crt`
   - Click 'Upload Certificate'

4. Configurar `settings.py` o `.env` con credenciales reales:

```python
# betfair_bot/settings.py o usar .env
BETFAIR_USERNAME = 'tu_email_betfair'
BETFAIR_PASSWORD = 'tu_contraseña_betfair' 
BETFAIR_APP_KEY = 'tu_application_key'
BETFAIR_SANDBOX = False  # Cambiar a False para producción
```

### 🔄 PASO 6 - PRUEBAS INTEGRACIÓN
**Proceder una vez usuario proporcione credenciales:**

```bash
# 1. Prueba sandbox (apuestas falsas)
cd /var/www/predicta.com.co
python manage.py run_bot --dry-run --cycles 2

# 2. Prueba con datos reales (pero sin apostar)
python manage.py run_bot --dry-run

# 3. Si todo bien, producción (apuestas reales)
python manage.py run_bot --interval 30
```

### 🔄 PASO 7 - SYSTEMD SERVICE (ejecución 24/7)
**Crear archivo:** `/etc/systemd/system/predicta-betfair-bot.service`

```ini
[Unit]
Description=Predicta Betfair Bot
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=root
WorkingDirectory=/var/www/predicta.com.co
Environment=DJANGO_SETTINGS_MODULE=betfair_bot.settings
Environment=PYTHONPATH=/var/www/predicta.com.co
ExecStart=/var/www/predicta.com.co/venv/bin/python manage.py run_bot --interval 30
Restart=always
RestartSec=30
StandardOutput=journal
StandardError=journal
SyslogIdentifier=predicta-bot

[Install]
WantedBy=multi-user.target
```

**Comandos:**
```bash
# Cargar y habilitar servicio
sudo systemctl daemon-reload
sudo systemctl enable predicta-betfair-bot.service
sudo systemctl start predicta-betfair-bot.service

# Monitorear logs
sudo journalctl -u predicta-betfair-bot -f
```

## Decisiones Técnicas Adoptadas

### 1. Predictor 1X2 (Poisson based)
- **No reentrena modelos** - Respeta constraint
- Usa `SimplePredictionService.get_all_simple_predictions()` como caja negra
- Obtiene lambda_home, lambda_away de goles esperados
- Calcula P(Home Wins) = Σ P(h > a) for h,a ~ Poisson(λ_home, λ_away)
- Método matemático sólido y transaparente

### 2. Edge Calculation (Valor)
```
edge = prob_modelo - (1 / cuota_betfair)
```
- Edge ≥ 5% por defecto para colocar apuesta
- Ejemplo: Modelo predice 55% (0.55), Betfair cuota 2.0 (1/2.0 = 0.5)
- Edge = 0.55 - 0.5 = 0.05 (5% edge) → APOSTAR

### 3. Stake Management
- **Stake fijo porcentual**: 2% del balance por defecto
- **Límite absoluto**: $10 máximo por apuesta
- **Adjustment por edge**: Stake aumenta proporcionalmente con mayor edge
- **Balance protection**: No apuesta si balance < $20

### 4. Fuente de Partidos Próximos
**Prioridad:**
1. **Betfair API** (ideal - no tiene límites de requests)
2. **The Odds API** (fallback - 500 req/mes límite)

### 5. Control de Riesgo
- **Sandbox mode**: BETFAIR_SANDBOX=True para desarrollo
- **Dry-run**: `--dry-run` flag para simular sin apostar
- **Rate limiting**: Built-in en betfairlightweight
- **Error tolerance**: Código robusto con try-except extensivo

## Testing Checklist

Antes de pasar a producción:

1. [ ] Credenciales Betfair configuradas
2. [ ] Prueba sandbox: `python manage.py run_bot --dry-run`
3. [ ] Verificar predicciones 1X2 en logs
4. [ ] Verificar conexión Betfair (login exitoso)
5. [ ] Calcular edge con datos de ejemplo
6. [ ] Prueba apuesta simulada
7. [ ] Verificar logs en `/var/log/predicta/`
8. [ ] Configurar alertas Telegram (opcional)

## Monitoreo

### Logs principales:
```
/var/log/predicta/betting_bot.log
/var/log/predicta/betting_bot_django.log
journalctl -u predicta-betfair-bot -f
```

### Métricas clave:
- Partidos analizados por ciclo
- Valor encontrado (apuestas identificadas)
- Edge promedio
- Stake colocado
- Balance actual

## Seguridad

1. **Certificados SSL**: 2048-bit RSA en `/etc/betfair/certs/`
2. **Permisos**: 600 para archivos `.key` y `.pem`
3. **Variables de ambiente**: Credenciales en `.env` (no en código)
4. **Sandbox default**: Seguro para desarrollo
5. **Log seguros**: No loguear credenciales

## Roadmap Sugerido (Post-implementación)

1. **Optimización**: 
   - Cache de predicciones por equipo
   - Pre-fetch de datos históricos
   - Database indexing para queries frecuentes

2. **Features avanzadas**:
   - Multi-model ensemble (usar varios modelos)
   - Time-weighted predictions (más peso a partidos recientes)
   - Market depth analysis (considerar liquidez)
   - Stop-loss / Take-profit automático

3. **Monitoreo dashboards**:
   - Django admin extension para ver apuestas
   - Dashboard de performance del bot
   - ROI tracking y analytics
   - Telegram bot para alerts en tiempo real

## Archivos Clave Creados

```
predicta.com.co/
├── .env.example                    # Template credenciales
├── betting_bot/
│   └── main.py                     # Orquestador principal
├── betting/
│   ├── predictors.py               # Predictor 1X2 (nuevo)
│   └── management/
│       └── commands/
│           └── run_bot.py          # Comando Django
├── betfair/
│   └── services.py                 # Actualizado para certs SSL
└── docs/betting_bot_setup.md       # Este documento
```

---

**ESTADO: LISTO PARA CREDENCIALES Y PRUEBAS**

El sistema está preparado técnicamente. Una vez el usuario proporcione las credenciales Betfair y The Odds API, se procederá con:
1. Pruebas sandbox
2. Ajustes de umbrales y stake
3. Deploy a producción con systemd
4. Monitoreo continuo