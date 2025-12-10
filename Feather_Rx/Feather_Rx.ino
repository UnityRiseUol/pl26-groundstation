#include <SPI.h>
#include <LoRa.h>

// --- PINS FOR ADAFRUIT FEATHER RP2040 ---
#define RFM95_CS    16
#define RFM95_RST   17
#define RFM95_INT   21

// Frequency: Must match the sender!
#define BAND 868E6

void setup() {
  Serial.begin(115200);
  while (!Serial) delay(1);

  Serial.println("Feather RP2040 LoRa Receiver");

  // Setup LoRa module
  LoRa.setPins(RFM95_CS, RFM95_RST, RFM95_INT);

  if (!LoRa.begin(BAND)) {
    Serial.println("Starting LoRa failed!");
    while (1);
  }
  
  // Note: Receiver doesn't need setTxPower, but it doesn't hurt.
  Serial.println("LoRa Receiver Listening at 868MHz...");
}

void loop() {
  // Try to parse packet
  int packetSize = LoRa.parsePacket();
  if (packetSize) {
    // Received a packet
    Serial.print("Received packet '");

    // Read packet
    while (LoRa.available()) {
      Serial.print((char)LoRa.read());
    }

    // Print RSSI (Signal Strength)
    Serial.print("' with RSSI ");
    Serial.println(LoRa.packetRssi());
  }
}