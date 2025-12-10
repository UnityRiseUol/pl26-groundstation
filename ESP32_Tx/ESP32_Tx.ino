#include <SPI.h>
#include <LoRa.h>

// --- WIRING FOR SPARKFUN ESP32-S3 ---
// CS=4, RST=1, INT=2
#define RFM95_CS    4
#define RFM95_RST   1
#define RFM95_INT   2

// SPI Pins
#define SCK_PIN     12
#define MISO_PIN    13
#define MOSI_PIN    11

// Frequency: 868E6 for Europe, 915E6 for USA
#define BAND 868E6 

void setup() {
  Serial.begin(115200);
  while (!Serial) delay(1);

  Serial.println("ESP32-S3 LoRa Transmitter");

  // 1. Force SPI pins
  SPI.begin(SCK_PIN, MISO_PIN, MOSI_PIN, RFM95_CS);
  LoRa.setSPI(SPI);

  // 2. Setup Radio Pins
  LoRa.setPins(RFM95_CS, RFM95_RST, RFM95_INT);

  // 3. Initialize Radio
  if (!LoRa.begin(BAND)) {
    Serial.println("Starting LoRa failed!");
    while (1);
  }

  // 4. Set High Power (20dBm)
  LoRa.setTxPower(20);

  Serial.println("LoRa Initialized at 868MHz High Power!");
}

int counter = 0;

void loop() {
  Serial.print("Sending packet: ");
  Serial.println(counter);

  // Send packet
  LoRa.beginPacket();
  LoRa.print("ESP32 Message ");
  LoRa.print(counter);
  LoRa.endPacket();

  counter++;
  delay(1000); // Send every 1 second
}