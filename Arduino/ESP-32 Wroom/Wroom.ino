#include <WiFi.h>
#include <WiFiUdp.h>
#include <HTTPClient.h>
#include <driver/i2s.h>
#include <driver/adc.h> // --- FIX 1: Include the ESP32 ADC driver ---

// --- CONFIG ---
const char* ssid     = "ARYAN's Galaxy M31";
const char* password = "Aryan@123";
const char* PC_IP    = "10.239.67.147"; // Make sure this is your PC's CURRENT IP
#define PC_API_PORT      5000
#define MIC_UDP_PORT     4444
#define SPK_UDP_PORT     5555
#define SMOKE_PIN        34
#define SMOKE_UDP_PORT   6666

#define I2S_MIC_WS 15
#define I2S_MIC_SD 32
#define I2S_MIC_SCK 14
#define I2S_MIC_NUM I2S_NUM_0
#define I2S_SPK_BCLK 26
#define I2S_SPK_LRC 25
#define I2S_SPK_DIN 22
#define I2S_SPK_NUM I2S_NUM_1
#define BUFFER_LEN 512

WiFiUDP udp_mic;
WiFiUDP udp_spk;
WiFiUDP udp_smoke;

int32_t raw_samples[BUFFER_LEN];
int16_t tx_samples[BUFFER_LEN];
uint8_t rx_buffer[1024];

void micTask(void* parameter) {
  Serial.println("🎤 Mic Task Started on Core 0");
  while (true) {
    size_t bytes_read = 0;
    esp_err_t result = i2s_read(I2S_MIC_NUM, &raw_samples, sizeof(raw_samples), &bytes_read, 100);
    if (result == ESP_OK && bytes_read > 0) {
      int samples = bytes_read / 4;
      for (int i=0; i<samples; i++) tx_samples[i] = (raw_samples[i] >> 14);
      udp_mic.beginPacket(PC_IP, MIC_UDP_PORT);
      udp_mic.write((uint8_t*)tx_samples, samples * 2);
      udp_mic.endPacket();
    }
    vTaskDelay(pdMS_TO_TICKS(10));
  }
}

// --- FIX 1: smokeTask uses native ADC functions ---
void smokeTask(void* parameter) {
  Serial.println("🔥 Smoke Task Started on Core 0");
  
  // Configure the ADC
  adc1_config_width(ADC_WIDTH_BIT_12); // 12-bit resolution (0-4095)
  // GPIO 34 is ADC1_CHANNEL_6. Use 11dB attenuation for full 0-3.3V range.
  adc1_config_channel_atten(ADC1_CHANNEL_6, ADC_ATTEN_DB_11); 
  
  while (true) {
    // 1. Read the raw analog value (0-4095)
    int smokeValue = adc1_get_raw(ADC1_CHANNEL_6);
    

    // Serial.print("Smoke Task: Reading value = ");
    // Serial.println(smokeValue);
    // 3. Send it as a UDP packet to the PC
    // (Using .print() is more efficient than sprintf for a simple int)
    udp_smoke.beginPacket(PC_IP, SMOKE_UDP_PORT);
    udp_smoke.print(smokeValue);
    udp_smoke.endPacket();

    // 4. Send data only every 2 seconds
    vTaskDelay(pdMS_TO_TICKS(2000)); 
  }
}

// --- FIX 2: spkTask ALWAYS delays 1ms ---
void spkTask(void* parameter) {
  Serial.println("🔊 Speaker Task Started on Core 1");
  if(udp_spk.begin(SPK_UDP_PORT)) {
       Serial.println("✅ UDP Listener started on port " + String(SPK_UDP_PORT));
  } else {
       Serial.println("❌ UDP Listener FAILED!");
  }
  
  while (true) {
    int packetSize = udp_spk.parsePacket();
    
    if (packetSize > 0) {
      int len = udp_spk.read(rx_buffer, sizeof(rx_buffer));
      if (len > 0) {
        size_t written;
        i2s_write(I2S_SPK_NUM, rx_buffer, len, &written, 100);
      }
    }
    
    // This MUST be outside the if/else block.
    // The task must ALWAYS yield (sleep) for at least 1ms
    // to prevent a Watchdog Timeout crash.
    vTaskDelay(pdMS_TO_TICKS(1)); 
  }
}

void setup() {
  // Disable Brownout Detector
  #include "soc/soc.h"
  #include "soc/rtc_cntl_reg.h"
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);

  Serial.begin(115200);
  delay(1000); // Shorter delay
  Serial.println("\n\n🔄 --- SYSTEM BOOT START ---");

  // 1. WiFi
  Serial.print("📶 Connecting to WiFi...");
  WiFi.begin(ssid, password);
  int tries = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(500); Serial.print(".");
    if (tries++ > 20) { Serial.println("\n❌ WiFi Failed! Restarting..."); ESP.restart(); }
  }
  Serial.println("\n✅ WiFi Connected: " + WiFi.localIP().toString());

  // 2. Mic Setup
  Serial.println("🔧 Configuring Microphone I2S...");
  i2s_config_t mic_cfg = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = 16000, .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT, .communication_format = I2S_COMM_FORMAT_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1, .dma_buf_count = 4, .dma_buf_len = BUFFER_LEN,
    .use_apll = false, .tx_desc_auto_clear = false, .fixed_mclk = 0
  };
  i2s_pin_config_t mic_pins = { .mck_io_num = I2S_PIN_NO_CHANGE, .bck_io_num = I2S_MIC_SCK, .ws_io_num = I2S_MIC_WS, .data_out_num = -1, .data_in_num = I2S_MIC_SD };
  i2s_driver_install(I2S_MIC_NUM, &mic_cfg, 0, NULL);
  i2s_set_pin(I2S_MIC_NUM, &mic_pins);

  // 3. Speaker Setup
  Serial.println("🔧 Configuring Speaker I2S...");
  i2s_config_t spk_cfg = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = 32000,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = (i2s_comm_format_t)(I2S_COMM_FORMAT_I2S | I2S_COMM_FORMAT_I2S_MSB),
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 10,
    .dma_buf_len = 1024,
    .use_apll = true,
    .tx_desc_auto_clear = true,
    .fixed_mclk = 0
  };
  
  i2s_pin_config_t spk_pins = { .mck_io_num = I2S_PIN_NO_CHANGE, .bck_io_num = I2S_SPK_BCLK, .ws_io_num = I2S_SPK_LRC, .data_out_num = I2S_SPK_DIN, .data_in_num = -1 };
  i2s_driver_install(I2S_SPK_NUM, &spk_cfg, 0, NULL);
  i2s_set_pin(I2S_SPK_NUM, &spk_pins);

  // 4. Start Tasks
  Serial.println("🚀 Starting RTOS Tasks...");
  // Give tasks slightly more stack for safety
  xTaskCreatePinnedToCore(micTask, "MicTask", 8000, NULL, 1, NULL, 0);
  xTaskCreatePinnedToCore(smokeTask, "SmokeTask", 4000, NULL, 1, NULL, 0);
  xTaskCreatePinnedToCore(spkTask, "SpkTask", 8000, NULL, 1, NULL, 1);
  
  Serial.println("✨ SYSTEM BOOT COMPLETE ✨");
}

void loop() {
  vTaskDelay(pdMS_TO_TICKS(1000)); // Main loop sleeps
}