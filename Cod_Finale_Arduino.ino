#include <Arduino.h>
#include <math.h>
#include "BluetoothSerial.h"

BluetoothSerial SerialBT;

// =======================
// PIN E HARDWARE
// =======================
const int PIN_SENSORE_UMIDITA = 35; // ADC1
const int PIN_SENSORE_TEMP   = 33; // ADC1
const int PIN_LED            = 18;

// =======================
// PWM LED
// =======================
const int PWM_CHANNEL = 0;
const int PWM_FREQ    = 5000;
const int PWM_RES     = 8;
const float LED_GAIN  = 0.35f;

// =======================
// UMIDITÀ (CALIBRAZIONE)
// =======================
const int UMID_SECCO   = 3600;
const int UMID_BAGNATO = 1400;

// =======================
// INTERVALLO INVIO DATI (secondi)
// modificabile da Python via Bluetooth
// =======================
volatile int Xs = 1;

// =======================
// VARIABILI CONDIVISE
// =======================
volatile float temperatura_globale = NAN;
volatile int   umidita_globale     = 0;

// =======================
// TASK HANDLE
// =======================
TaskHandle_t TaskCore0;
TaskHandle_t TaskCore1;

// =======================
// CORE 0 – SENSORI + LED
// =======================
void aggiornaUmidita() {
    static float adc_filtrato = 0.0f;
    const float ALPHA = 0.15f;

    int adc = analogRead(PIN_SENSORE_UMIDITA);
    adc = constrain(adc, UMID_BAGNATO, UMID_SECCO);

    if (adc_filtrato == 0.0f)
        adc_filtrato = adc;
    else
        adc_filtrato = ALPHA * adc + (1.0f - ALPHA) * adc_filtrato;

    float percent = 100.0f * (UMID_SECCO - adc_filtrato) /
                    (UMID_SECCO - UMID_BAGNATO);

    percent = constrain(percent, 0.0f, 100.0f);
    umidita_globale = (int)(percent + 0.5f);

    // ----- LED PWM -----
    float percent_led = percent * percent / 100.0f;
    int pwm_val = (int)(255.0f * percent_led / 100.0f * LED_GAIN);
    pwm_val = constrain(pwm_val, 0, 255);
    ledcWrite(PWM_CHANNEL, pwm_val);

    Serial.printf(
        "[CORE0][UMID] ADC=%d | %%=%d | PWM=%d\n",
        adc, umidita_globale, pwm_val
    );
}

void aggiornaTemperatura() {
    int adc = analogRead(PIN_SENSORE_TEMP);

    if (adc < 5) {
        temperatura_globale = NAN;
        return;
    }

    double voltage = (double)adc / 4095.0 * 3.3;
    voltage = max(voltage, 0.01);

    double Rt = 10.0 * voltage / (3.3 - voltage);
    double tempK = 1.0 / ((1.0 / (273.15 + 25.0)) +
                    log(Rt / 10.0) / 3950.0);

    temperatura_globale = tempK - 273.15;

    Serial.printf(
        "[CORE0][TEMP] %.2f °C\n",
        temperatura_globale
    );
}

// =======================
// TASK CORE 0
// =======================
void TaskCore0code(void* pvParameters) {
    const TickType_t DELAY = 125 / portTICK_PERIOD_MS;
    bool leggiUmidita = true;

    for (;;) {
        if (leggiUmidita)
            aggiornaUmidita();
        else
            aggiornaTemperatura();

        leggiUmidita = !leggiUmidita;
        vTaskDelay(DELAY);
    }
}

// =======================
// TASK CORE 1 – BLUETOOTH
// =======================
void TaskCore1code(void* pvParameters) {
    unsigned long lastSend = 0;

    for (;;) {

        // ---- Ricezione comandi ----
        if (SerialBT.available()) {
            String cmd = SerialBT.readStringUntil('\n');
            cmd.trim();

            if (cmd.startsWith("SET_XS=")) {
                int nuovoXs = cmd.substring(7).toInt();
                if (nuovoXs > 0 && nuovoXs <= 60) {
                    Xs = nuovoXs;
                    SerialBT.println("OK;XS=" + String(Xs));
                }
            }
        }

        // ---- Invio dati ----
        if (millis() - lastSend >= (unsigned long)Xs * 1000) {
            lastSend = millis();

            SerialBT.print("DATA;");
            SerialBT.print("T=");
            if (isnan(temperatura_globale))
                SerialBT.print("null");
            else
                SerialBT.print(temperatura_globale, 2);

            SerialBT.print(";H=");
            SerialBT.println(umidita_globale);
        }

        vTaskDelay(20 / portTICK_PERIOD_MS);
    }
}

// =======================
// SETUP
// =======================
void setup() {
    Serial.begin(115200);

    SerialBT.begin("ESP32_TempHum");
    Serial.println("Bluetooth pronto");

    analogReadResolution(12);
    analogSetAttenuation(ADC_11db);

    ledcSetup(PWM_CHANNEL, PWM_FREQ, PWM_RES);
    ledcAttachPin(PIN_LED, PWM_CHANNEL);

    xTaskCreatePinnedToCore(
        TaskCore0code,
        "Sensori",
        4096,
        nullptr,
        1,
        &TaskCore0,
        0
    );

    xTaskCreatePinnedToCore(
        TaskCore1code,
        "Bluetooth",
        4096,
        nullptr,
        1,
        &TaskCore1,
        1
    );
}

void loop() {}