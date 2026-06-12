/*
 * Program: PLOTS_Offline_UART_Test.cpp
 * Receiver: Adafruit Feather RP2040
 */

#include <Arduino.h>

unsigned long lastSimTime = 0;
const int SIM_INTERVAL_MS = 33;
float simTimeSec = 0.0f;

void setup() 
{
    Serial1.setTX(0);//GPIO 0 TX
    Serial1.setRX(1);//GPIO 1 RX
    Serial1.begin(115200);
    
    //USB serial
    Serial.begin(115200);
    
    delay(2000);
    Serial.println("Sending telemetry to BOTH USB and TX Pin...");
}

void loop() {
    unsigned long currentMillis = millis();

    if (currentMillis - lastSimTime >= SIM_INTERVAL_MS) 
    {
        lastSimTime = currentMillis;
        simTimeSec += (SIM_INTERVAL_MS / 1000.0f);

        //Simulate parabolic fake flight
        float altitude = max(0.0f, 150.0f * simTimeSec - 4.9f * simTimeSec * simTimeSec);
        float vSpeed = (altitude > 0) ? (150.0f - 9.8f * simTimeSec) : 0.0f;

        if (altitude == 0 && simTimeSec > 10.0f)
        {
            simTimeSec = 0.0f; //Reset simulation
        }

        //Simulate GPS
        float lat = 52.668f + (simTimeSec * 0.00001f);
        float lon = -1.5245f + (sin(simTimeSec) * 0.00001f);

        //Simulate quaternion rotation
        float qR = cos(simTimeSec * 0.5f);
        float qI = sin(simTimeSec * 0.5f);
        float qJ = 0.0f;
        float qK = 0.0f;

        //Simulate INS and RSSI
        float insX = sin(simTimeSec) * 20.0f;
        float insY = cos(simTimeSec) * 20.0f;
        float insZ = altitude;
        int rssi = -60 + (rand() % 10 - 5);

        String telemetry = String(currentMillis) + "," + 
                           String(altitude, 2) + "," + 
                           String(vSpeed, 2) + "," + 
                           String(lat, 6) + "," + 
                           String(lon, 6) + "," + 
                           String(qR, 4) + "," + 
                           String(qI, 4) + "," + 
                           String(qJ, 4) + "," + 
                           String(qK, 4) + "," + 
                           String(insX, 2) + "," + 
                           String(insY, 2) + "," + 
                           String(insZ, 2) + "," + 
                           String(rssi);

        Serial1.println(telemetry);//Send to UART
        Serial.println(telemetry);//Send USB
    }
}