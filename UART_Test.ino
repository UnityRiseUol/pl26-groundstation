#include <Arduino.h>

#define UART_BAUD 115200
#define SEND_INTERVAL_MS 30

unsigned long startTime;
unsigned long lastSend = 0;
float altitude = 0.0;
float velocity = 0.0;
float accel    = 25.0;
bool burnout   = false;
bool apogee    = false;

void setup()
{
  Serial.begin(115200);
  Serial1.begin(UART_BAUD);

  startTime = millis();
  Serial.println("Feather Fake Telemetry Started (UART)");
}

void loop()
{
  unsigned long now = millis();

  if (now - lastSend >= SEND_INTERVAL_MS)
  {
    lastSend = now;

    float dt = SEND_INTERVAL_MS / 1000.0;
    float t  = (now - startTime) / 1000.0;

    if (t < 3.0)
    {
      velocity += accel * dt;
    }
    else
    {
      burnout = true;
      velocity -= 9.81 * dt;
    }

    altitude += velocity * dt;

    if (burnout && velocity <= 0)
      apogee = true;

    if (altitude < 0)
      altitude = 0;

    float latitude  = 34.021300 + altitude * 1e-6;
    float longitude = -117.123400 + altitude * 1e-6;

    int LDA     = 0;
    int LowV    = 0;
    int Apogee  = apogee ? 1 : 0;
    int NO      = 1;
    int Drogue  = apogee ? 1 : 0;
    int Main    = (altitude < 150 && apogee) ? 1 : 0;

    //CSV packet
    Serial1.print(t, 3);           Serial1.print(",");
    Serial1.print(altitude, 2);    Serial1.print(",");
    Serial1.print(velocity, 2);    Serial1.print(",");
    Serial1.print(altitude, 2);    Serial1.print(",");
    Serial1.print(velocity, 2);    Serial1.print(",");
    Serial1.print(LDA);            Serial1.print(",");
    Serial1.print(LowV);           Serial1.print(",");
    Serial1.print(Apogee);         Serial1.print(",");
    Serial1.print(NO);             Serial1.print(",");
    Serial1.print(Drogue);         Serial1.print(",");
    Serial1.print(Main);           Serial1.print(",");
    Serial1.print(latitude, 6);    Serial1.print(",");
    Serial1.print(longitude, 6);   Serial1.print(",");
    Serial1.print(abs(velocity), 2); Serial1.print(",");
    Serial1.println(90.0);
  }
}
