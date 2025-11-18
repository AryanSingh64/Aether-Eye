#include "esp_camera.h"
#include <WiFi.h>

// ===========================
// Select camera model in board_config.h
// ===========================
#include "board_config.h"

void startCameraServer();
void setupLedFlash();

const char* ssid     = "ARYAN's Galaxy M31";
const char* password = "Aryan@123";

void setup() {
  Serial.begin(115200);
  Serial.setDebugOutput(true);
  Serial.println();

camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk     = XCLK_GPIO_NUM;
  config.pin_pclk     = PCLK_GPIO_NUM;
  config.pin_vsync    = VSYNC_GPIO_NUM;
  config.pin_href     = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;
  
  // 1. STABILITY FIX: Keep XCLK at 20MHz to stop I2C NACK errors
  config.xclk_freq_hz = 20000000; 
  
  // 2. SPEED FIX: Do not use UXGA. Use VGA (640x480) or SVGA (800x600)
  // VGA is plenty for AI/YOLO and gives smooth 15-25 FPS.
  config.frame_size   = FRAMESIZE_VGA; 
  
  config.pixel_format = PIXFORMAT_JPEG; 
  config.grab_mode    = CAMERA_GRAB_LATEST; // Always grab the newest frame
  config.fb_location  = CAMERA_FB_IN_PSRAM;
  
  // 3. BANDWIDTH FIX: Increase compression slightly (10-63, lower is better quality)
  // 12 is very high quality (slow). 15-20 is faster streaming.
  config.jpeg_quality = 14; 
  
  config.fb_count     = 2; // Double buffering

  if (config.pixel_format == PIXFORMAT_JPEG) {
    if (psramFound()) {
      config.jpeg_quality = 10;
      config.fb_count = 2;
      config.grab_mode = CAMERA_GRAB_LATEST;
    } else {
      // Limit the frame size when PSRAM is not available
      config.frame_size = FRAMESIZE_SVGA;
      config.fb_location = CAMERA_FB_IN_DRAM;
    }
  }

  // camera init
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x", err);
    return;
  }

  sensor_t *s = esp_camera_sensor_get();
  
  // =========================================
  // OV3660 SPECIFIC CORRECTIONS
  // =========================================
  if (s->id.PID == OV3660_PID) {
    s->set_vflip(s, 1);        // Flip vertical
    s->set_brightness(s, 1);   // Boost brightness
    s->set_saturation(s, -2);  // Reduce saturation (fixes green tint)
  }
  
  // Standard AI Thinker Flip (if image is upside down, change to 0)
  s->set_vflip(s, 1);
  s->set_hmirror(s, 1);

#if defined(LED_GPIO_NUM)
  setupLedFlash();
#endif

  WiFi.begin(ssid, password);
  WiFi.setSleep(false);

  Serial.print("WiFi connecting");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("");
  Serial.println("WiFi connected");

  startCameraServer();

  Serial.print("Camera Ready! Use 'http://");
  Serial.print(WiFi.localIP());
  Serial.println("' to connect");
}

void loop() {
  delay(10000);
}