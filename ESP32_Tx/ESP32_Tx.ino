#include <SPI.h>
#include <LoRa.h>

#define RFM95_CS    7
#define RFM95_RST   5
#define RFM95_INT   6

#define SCK_PIN     12
#define MISO_PIN    13
#define MOSI_PIN    11

#define BAND 868E6 

void setup() {
  Serial.begin(115200);
  while (!Serial) delay(1);

  Serial.println("ESP32-S3 LoRa Transmitter");

  SPI.begin(SCK_PIN, MISO_PIN, MOSI_PIN, RFM95_CS);
  LoRa.setSPI(SPI);

  LoRa.setPins(RFM95_CS, RFM95_RST, RFM95_INT);

  if (!LoRa.begin(BAND)) {
    Serial.println("Starting LoRa failed!");
    while (1);
  }

  LoRa.setTxPower(20);

  Serial.println("LoRa Initialized at 868MHz High Power!");
}

int counter = 0;

void loop() {
  Serial.print("Sending packet: ");
  Serial.println(counter);

  LoRa.beginPacket();
  LoRa.print("ESP32 Message ");
  LoRa.print(counter);
  LoRa.endPacket();

  counter++;
  delay(1000);
}