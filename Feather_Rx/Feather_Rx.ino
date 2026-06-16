/*
 * File:        main.cpp
 * Receiver:    Adafruit Feather RP2040
 * Description: High Speed LoRa Receiver with Buffer Flushing (Flight Phase + Dual Output)
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
    int32_t flightPhase;
};

static_assert(sizeof(TelemetryPacket) == 48, "TelemetryPacket must remain 48 bytes");

unsigned long lastStatTime = 0;
int packetCount = 0;
TelemetryPacket currentPacket;

void setup() {
    Serial.begin(115200); // Standard hardware USB CDC
    Serial1.begin(115200); // Hardware TX/RX pins
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

            // ------------------------------------------------------------------
            // 1. Output to Raspberry Pi via Jumper Wires (Serial1)
            // ------------------------------------------------------------------
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
            Serial1.print(currentPacket.flightPhase); Serial1.print(","); // <-- Flight Phase Included
            Serial1.println(LoRa.packetRssi());

            // ------------------------------------------------------------------
            // 2. Output to Computer/Pi via USB Cable (Serial)
            // ------------------------------------------------------------------
            Serial.print(millis()); Serial.print(",");
            Serial.print(currentPacket.altitude, 2); Serial.print(",");
            Serial.print(currentPacket.vSpeed, 2); Serial.print(",");
            Serial.print(currentPacket.lat, 6); Serial.print(",");
            Serial.print(currentPacket.lon, 6); Serial.print(",");
            Serial.print(currentPacket.qR, 4); Serial.print(",");
            Serial.print(currentPacket.qI, 4); Serial.print(",");
            Serial.print(currentPacket.qJ, 4); Serial.print(",");
            Serial.print(currentPacket.qK, 4); Serial.print(",");
            Serial.print(currentPacket.insX, 2); Serial.print(",");
            Serial.print(currentPacket.insY, 2); Serial.print(",");
            Serial.print(currentPacket.insZ, 2); Serial.print(",");
            Serial.print(currentPacket.flightPhase); Serial.print(","); // <-- Flight Phase Included
            Serial.println(LoRa.packetRssi());
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
            // Print warning to USB only so it doesn't break the Pi's CSV parser
            Serial.println(">>> RATE: 0 Hz (Check Sender) <<<");
        } else {
            // Print rate to USB only
            Serial.print("Rate: "); Serial.println(packetCount);
        }
        packetCount = 0;
        lastStatTime = millis();
    }
}