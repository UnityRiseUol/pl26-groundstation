/*
 * File:        main.cpp
 * Receiver:    Adafruit Feather RP2040
 * Description: High Speed LoRa Receiver (Binary/Struct)
 */

#include <Arduino.h>
#include <SPI.h>
#include <LoRa.h>

// --- PINS (Feather RP2040) ---
#define RFM95_CS    16
#define RFM95_RST   17
#define RFM95_INT   21
#define BAND 868E6

// --- STRUCT DEFINITION ---
// MUST match the Sender exactly!
struct __attribute__((packed)) TelemetryPacket {
    float altitude;   // 4 bytes
    float v_speed;    // 4 bytes
    float lat;        // 4 bytes
    float lon;        // 4 bytes
    float qR;         // 4 bytes
    float qI;         // 4 bytes
    float qJ;         // 4 bytes
    float qK;         // 4 bytes
}; // Total 32 bytes

// --- STATISTICS ---
unsigned long lastStatTime = 0;
int packetCount = 0;
TelemetryPacket currentPacket;

void setup() {
  Serial.begin(115200);
  // while (!Serial) delay(1); // Optional: Wait for USB

  Serial.println("RP2040 LoRa Receiver - High Speed Mode");

  // Setup LoRa
  LoRa.setPins(RFM95_CS, RFM95_RST, RFM95_INT);
  if (!LoRa.begin(BAND)) {
    Serial.println("LoRa Init Failed");
    while (1);
  }

  // --- MATCH SENDER SETTINGS EXACTLY ---
  LoRa.setSignalBandwidth(500E3); // 500kHz
  LoRa.setSpreadingFactor(7);     // SF7
  LoRa.setCodingRate4(5);         // CR 4/5
  
  Serial.println("LoRa Listening at 868MHz / 500kHz BW...");
}

void loop() {
  // Check for packet
  int packetSize = LoRa.parsePacket();

  if (packetSize == sizeof(TelemetryPacket)) {
    // Read the binary data directly into the struct
    LoRa.readBytes((uint8_t*)&currentPacket, sizeof(currentPacket));
    packetCount++;

    // Print Data in CSV format for plotting
    Serial.print(millis());
    Serial.print(",");
    Serial.print(currentPacket.altitude);
    Serial.print(",");
    Serial.print(currentPacket.v_speed);
    Serial.print(",");
    Serial.print(currentPacket.lat, 6);
    Serial.print(",");
    Serial.print(currentPacket.lon, 6);
    Serial.print(",");
    Serial.print(currentPacket.qR);
    Serial.print(",");
    Serial.print(currentPacket.qI);
    Serial.print(",");
    Serial.print(currentPacket.qJ);
    Serial.print(",");
    Serial.print(currentPacket.qK);
    Serial.print(",");
    Serial.println(LoRa.packetRssi());

  } else if (packetSize > 0) {
    // Received something, but size is wrong (likely interference or old packet format)
    Serial.print("ERR: Size mismatch. Got: ");
    Serial.println(packetSize);
    
    // Clear buffer
    while (LoRa.available()) LoRa.read();
  }

  // Print Frequency Stats every 1 second
  if (millis() - lastStatTime >= 1000) {
    Serial.print(">>> RATE: ");
    Serial.print(packetCount);
    Serial.println(" Hz <<<");
    
    packetCount = 0;
    lastStatTime = millis();
  }
}