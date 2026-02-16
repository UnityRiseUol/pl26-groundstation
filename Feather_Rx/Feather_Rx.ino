/*
 * File:        main.cpp
 * Receiver:    Adafruit Feather RP2040
 * Description: High Speed LoRa Receiver with Buffer Flushing
 */

#include <Arduino.h>
#include <SPI.h>
#include <LoRa.h>

#define RFM95_CS    16
#define RFM95_RST   17
#define RFM95_INT   21
#define BAND 868E6

struct __attribute__((packed)) TelemetryPacket {
    float altitude;   
    float vSpeed;    
    float lat;        
    float lon;        
    float qR, qI, qJ, qK;         
    float insX, insY, insZ;       
};

unsigned long lastStatTime = 0;
int packetCount = 0;
TelemetryPacket currentPacket;

void setup() {
    Serial1.begin(115200);
    LoRa.setPins(RFM95_CS, RFM95_RST, RFM95_INT);
    
    if (!LoRa.begin(BAND)) {
        Serial.println("LoRa Init Failed");
        while (1);
    }

    // High Speed Configuration
    LoRa.setSignalBandwidth(500E3);
    LoRa.setSpreadingFactor(7);
    LoRa.setCodingRate4(5);
    LoRa.enableCrc(); // Matches sender
    
    Serial.println("RP2040 Receiver Ready. Syncing...");
}

void loop() {
    int packetSize = LoRa.parsePacket();

    if (packetSize > 0) {
        if (packetSize == sizeof(TelemetryPacket)) {
            // Read valid packet
            LoRa.readBytes((uint8_t*)&currentPacket, sizeof(currentPacket));
            packetCount++;

            // Print CSV (Millis, Alt, VSpd, Lat, Lon, Quats, INS_XYZ, RSSI)
            Serial1.print(millis()); Serial1.print(",");
            Serial1.print(currentPacket.altitude, 2); Serial1.print(",");
            Serial1.print(currentPacket.vSpeed, 2); Serial1.print(",");
            Serial1.print(currentPacket.lat, 6); Serial1.print(",");
            Serial1.print(currentPacket.lon, 6); Serial1.print(",");
            Serial1.print(currentPacket.qR, 4); Serial1.print(",");
            Serial1.print(currentPacket.qI, 4); Serial1.print(",");
            Serial1.print(currentPacket.qJ, 4); Serial1.print(",");
            Serial1.print(currentPacket.qK, 4); Serial1.print(",");
            Serial1.print(currentPacket.insX, 2); Serial1.print(",");
            Serial1.print(currentPacket.insY, 2); Serial1.print(",");
            Serial1.print(currentPacket.insZ, 2); Serial1.print(",");
            Serial1.println(LoRa.packetRssi());
        } 
        else {
            // BUFFER FLUSH: Prevents the "255" ghosting issue
            // If the size is wrong, empty the radio's buffer immediately
            while (LoRa.available()) {
                LoRa.read();
            }
        }
    }

    // Rate Stats (Printed only if no packets coming through)
    if (millis() - lastStatTime >= 1000) {
        if (packetCount == 0) {
            Serial.print(">>> RATE: 0 Hz (Check Sender) <<<");
        } else {
            Serial.print("Rate: "); Serial.println(packetCount);
        }
        packetCount = 0;
        lastStatTime = millis();
    }
}