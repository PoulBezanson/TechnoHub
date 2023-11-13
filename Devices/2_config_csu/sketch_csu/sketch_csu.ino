#include <ModbusRtu.h>
#include <SimpleKeypad.h>
#include <LCD_1602_RUS.h>
#include <MPU6050.h>
#include <LiquidCrystal_I2C.h>
#include <Wire.h>
#include <I2Cdev.h>


// Порты для подключения двигателей
#define MOTOR_A 6
#define MOTOR_B 7

#define MIN_POWER 70  // Минимальное управляющее воздействие, которое подается на двигатели
#define DEFAULT_BIAS 1949 // Целевое значение углового положения относительно платформы
                          
#define DEFAULT_CONTROL_PERIOD 10 // Период цикла управления по умолчанию

// размеры клавиатуры
#define KP_ROWS 1
#define KP_COLS 4

#define G 16384 // Ускорение свободного падения для акселерометра при диапазоне +-2g
#define horizontErr (-210) // Калибровочная поправка аксилирометра было 97

#define COUNT 5000  // Количество значений для горизонтирования

#define R 3.17  // Радиус колеса

#define HOLDING_REGS_SIZE 23 // Количество каналов для OPC сервера
#define ID   1      // Адрес МК для обмена данными с ОРС сервером

LCD_1602_RUS LCD(0x27, 16, 2);  // Объект для вывода информации на дисплей

MPU6050 mpu;  // Объект для работы с акселерометром

byte colPins[KP_COLS] = {39, 37,  33, 41}; // Порты подключения к клавиатуре
byte rowPins[KP_ROWS] = {35}; // GND для клавиатуры

char keys[KP_ROWS][KP_COLS] = { // Массив имён кнопок
  {'1', '2', '3', '4'}
};

SimpleKeypad pad((char*)keys, rowPins, colPins, KP_ROWS, KP_COLS);  // Объект для работы с клавиатурой

Modbus slave(ID, 0, 0);  // Объект для работы с ОРС сервером
int8_t state = 0; // Системная переменная состояния для работы с ОРС сервером

int controlPeriod = DEFAULT_CONTROL_PERIOD; // Переменная указывающая требуемый цикл управления
int SendOPC = 0;  // Признак режима с подключением к ОРС серверу
uint16_t holdingRegs[HOLDING_REGS_SIZE]; // Массив тегов

int EncoderPinMSB1 = 2; //датчик углового положение колеса //MSB = most significant bit
int EncoderPinLSB1 = 3; //датчик углового положение колеса //LSB = least significant bit  

volatile int lastEncoded1 = 0;
volatile int EncoderValue1 = 0; // начальное значение показания энкодера датчика углового положение колеса (имп)
volatile int prevEncoderValue1 = 0; // предыдущее значение показания энкодера датчика углового положение колеса (имп)
volatile double AngleValue1 = 0; // значение показания энкодера датчика углового положение колеса (гр)

int EncoderPinMSB2 = 19; //датчик углового положение ОУ //MSB = most significant bit
int EncoderPinLSB2 = 18; //датчик углового положение ОУ //LSB = least significant bit  

volatile int lastEncoded2 = 0; 
volatile int EncoderValue2 = 0; // значение показания энкодера датчика углового положение ОУ (имп)
volatile int prevEncoderValue2 = 0; // предыдущее значение показания инкодера датчика углового положение ОУ (имп)
volatile double AngleValue2 = 0; // значение показания энкодера датчика углового положение ОУ (гр)

int criticalAngle = 150;  // Критическое угловое отклонение по умолчанию соответствует 6.75 гр.
int criticalLinear = 1313; // Критическое линейное смещение по умолчанию соответствует 20 см.

unsigned long oldTimeStabilisation = 0; // Время начала предыдущего цикла управления
unsigned long periodStabilisation = 0;  // Действительное значение цикла управления
unsigned long oldMenuTime = 0;  // Время нахождения макета неподвижно
unsigned long startTime = 0;  // Время запуска СУД

long angle = 0; // Управляющее воздействие для алгоритма 1
long linearStabAngle = 0; // Управляющее воздействие для алгоритма 2
int angle_bias = DEFAULT_BIAS;  // Целевое угловое положение
int linear_bias = 0;  // Целевое линейное положение

int chooseAlgorithm = 0;  // Выбранный алгоритм

int flagPrint = 0;  // Признак вывода основого текста при включенной СУД на дисплей
int fixFlag = 0;  // Признак однозначного определения целевого угла

double kPangle = 5.0;  // Пропорциональный коэффициент ПИД2
double kIangle = 0.015; // Интегральный коэффициент ПИД2 
double kDangle = 3.5; // Дифференциальный коэффициент ПИД2

double kPlinear = 0.01; // Пропорциональный коэффициент ПИД1
double kIlinear = 0.0; // Интегральный коэффициент ПИД1
double kDlinear = 8.0; // Дифференциальный коэффициент ПИД1

double kPangle2 = 15.0;  // Пропорциональный коэффициент ПИД2
double kIangle2 = 0.0; // Интегральный коэффициент ПИД2 
double kDangle2 = 5.0; // Дифференциальный коэффициент ПИД2

double kPlinear2 = 1.5; // Пропорциональный коэффициент ПИД1
double kIlinear2 = 0.0; // Интегральный коэффициент ПИД1
double kDlinear2 = 1.0; // Дифференциальный коэффициент ПИД1


//инициализация исходной информации модели для регулятора 2
float Ae[2][2] = { -0.364912, 0.053954, -4.178116, 0.584912}; 
float He[2][2] = { -163.798085, 0.000018, -745.016628, 0.000055}; 
float Be[2] = { -0.000442, 0.003398}; 
float H[2][2] = {136.610714, -0.000013, 417.491017, 0}; 
float S[4] = { -1533, -252, -460 - 495};

//инициализация начальной информации для регулятора 2
float Xa[2] = {0, 0}; 
float Va[2] = {0, 0}; 
float X[4] = {0, 0, 0, 0}; 
float Y[2] = {0, 0}; 
volatile int U = 0; 

int maxLinear = 0;  // Максимально достигнутое смещение
int maxAngle = 0;  // Максимально достигнутое угловое отклонение
int prevMaxLinear = 0;  // Предыдущее максимально достигнутое смещение
int prevMaxAngle = 0;  // Предыдущее максимально достигнутое угловое отклонение

enum{ // Пространство состояний
  CALIBRATION,
  READY,
  STABILISATION,
  FALLED
} State;


long computePIDangle(int input, int setpoint, double kp, double ki, double kd, unsigned long dt, bool restartPID = false);
long computePIDlinear(int input, int setpoint, double kp, double ki, double kd, unsigned long dt, bool restartPID = false);

void setup() {
  TCCR4A = 0b00000011;  // Переключение ШИМ в разрешение 10 бит
  // включение диодов
  pinMode(47, OUTPUT); // желтый диод
  digitalWrite(47, HIGH);
  pinMode(45, OUTPUT); // зеленый диод
  digitalWrite(45, HIGH);
  pinMode(43, OUTPUT); // красный диод
  digitalWrite(43, HIGH);

  // Включение акселерометра
  pinMode(14, OUTPUT);
  pinMode(15, OUTPUT);
  digitalWrite(14, LOW);
  digitalWrite(15, HIGH);
  
  // Инициализация шины I2C
  Wire.begin();
  delay(500);
  mpu.initialize(); // Инициализация акселерометра
  LCD.init(); // инициализация LCD дисплея
  delay(100);
  LCD.backlight(); // включение подсветки дисплея
  State = CALIBRATION;
  
  // Подготовка к отправке данных
  holdingRegs[0] = EncoderValue2;
  holdingRegs[1] = angle_bias;
  holdingRegs[2] = EncoderValue1;
  holdingRegs[3] = linear_bias;
  holdingRegs[4] = chooseAlgorithm;
  holdingRegs[5] = (int)(kPangle*1000);
  holdingRegs[6] = (int)(kIangle*1000);
  holdingRegs[7] = (int)(kDangle*1000);
  holdingRegs[8] = (int)(kPlinear*1000);
  holdingRegs[9] = (int)(kIlinear*1000);
  holdingRegs[10] = (int)(kDlinear*1000);
  holdingRegs[11] = 0;
  holdingRegs[12] = 0;
  holdingRegs[13] = 0;
  holdingRegs[14] = 0;
  holdingRegs[15] = State;
  holdingRegs[16] = criticalAngle;
  holdingRegs[17] = criticalLinear;
  holdingRegs[18] = controlPeriod;
  holdingRegs[19] = periodStabilisation;
  
  // Отправка данных
  if(SendOPC = 1)
  {
    slave.begin( 115200 ); 
    slave.poll( holdingRegs, HOLDING_REGS_SIZE);
  }
  // Настройка портов для работы энкодеров
  pinMode(EncoderPinMSB1, INPUT); //датчик угла 1
  pinMode(EncoderPinLSB1, INPUT); //датчик угла 1
  pinMode(EncoderPinMSB2, INPUT); //датчик угла 2
  pinMode(EncoderPinLSB2, INPUT); //датчик угла 2
  
  digitalWrite(EncoderPinMSB1, HIGH); //turn pullup resistor on
  digitalWrite(EncoderPinLSB1, HIGH); //turn pullup resistor on
  digitalWrite(EncoderPinMSB2, HIGH); //turn pullup resistor on 
  digitalWrite(EncoderPinLSB2, HIGH); //turn pullup resistor on

  // Разрешение прерываний
  attachInterrupt(1, UpdateEncoder1, CHANGE); //EncoderPinLSB1=3 INT.1
  attachInterrupt(0, UpdateEncoder1, CHANGE); //EncoderPinMSB1=2 INT.0
  attachInterrupt(4, UpdateEncoder2, CHANGE); //EncoderPinMSB2=19 INT.4
  attachInterrupt(5, UpdateEncoder2, CHANGE); //EncoderPinLSB2=18 INT.5

  // Настройка портов для управления двигателями
  pinMode(MOTOR_A, OUTPUT);
  pinMode(MOTOR_B, OUTPUT);

  // Вывод текста на дисплей
  LCD.clear();
  LCD.setCursor(0, 0);
  LCD.print("leveling...");
  calibration();  // Запуск функции горизонтирования
  oldTimeStabilisation = millis();
  
  // Запуск последовательного порта для настройки вертикального состояния
  
}

void loop() {
  do{ // Пока время, прошедшее с начала цикла меньше, чем период цикла управления
    periodStabilisation = millis()-oldTimeStabilisation;
  }while(periodStabilisation < controlPeriod);
  oldTimeStabilisation = millis();
  
  switch(State){
    case READY: // Ожидание
        analogWrite(MOTOR_A, LOW);
        analogWrite(MOTOR_B, LOW);
        Serial.println(angle_bias);
        if(fixFlag == 0)  // Определение целевого угла, если не определен
        {
          if((EncoderValue2 < -50))
          {
            angle_bias = angle_bias - 3897;
            fixFlag = 1;
          }
          if((EncoderValue2 > 50))
            fixFlag = 1;
        }
        if(((prevEncoderValue1 >= EncoderValue1 + 10) || (prevEncoderValue1 <= EncoderValue1 - 10)) || ((prevEncoderValue2 >= EncoderValue2 + 10) || (prevEncoderValue2 <= EncoderValue2 - 10)))
        { // Параметры углового или линейного положения были изменены
          prevEncoderValue2 = EncoderValue2;
          prevEncoderValue1 = EncoderValue1;
          oldMenuTime = millis();
        }

        if(millis() - oldMenuTime < 3000)
        { // Вывод параметров углового или линейного положения
          LCD.setCursor(0, 0); // ставим курсор на 1 символ первой строки
          LCD.print("Pos: "); // печатаем сообщение на первой строке
          LCD.print((2 * R * 3.1415 * (EncoderValue1 - linear_bias) / 1320)); // печатаем сообщение на первой строке
          LCD.print(" cm    "); // печатаем сообщение на первой строке
          LCD.setCursor(0, 1); // ставим курсор на 1 символ первой строки
          LCD.print("Ang: "); // печатаем сообщение на первой строке
        }
        else
        { // Вывод меню
          LCD.setCursor(0, 0); // ставим курсор на 1 символ первой строки
          if(chooseAlgorithm == 0)
            LCD.print("Algorithm 1  (1)"); // печатаем сообщение на первой строке
          else
            LCD.print("Algorithm 2  (1)"); // печатаем сообщение на первой строке
          LCD.setCursor(0, 1); // ставим курсор на 1 символ первой строки
          if(SendOPC == 1)
            LCD.print("SCADA on     (2)"); // печатаем сообщение на первой строке
          else
            LCD.print("SCADA off    (2)"); // печатаем сообщение на первой строке
        }        
        if(fixFlag == 0)
        { // Целевой угол не определен
          LCD.print("---"); // печатаем сообщение на первой строке
        }
        else
        {
          LCD.print((double)degrees(2 * 3.1415 * (EncoderValue2 - angle_bias) / 8000)); // печатаем сообщение на первой строке
          LCD.write(223); 
          LCD.print("     "); // печатаем сообщение на первой строке
        }
        if((EncoderValue2 >= angle_bias - 22) && (EncoderValue2 <= angle_bias + 22))
//        if((EncoderValue2 >= angle_bias - 22) && (EncoderValue2 <= angle_bias + 22) && (EncoderValue1 >= linear_bias - 22) && (EncoderValue1 <= linear_bias + 22))
        { // Переход в состояние стабилизации
          State = STABILISATION;
          LCD.clear();
          LCD.setCursor(0, 0); // ставим курсор на 1 символ первой строки
          LCD.print("  CSU on"); // печатаем сообщение на первой строке
          oldTimeStabilisation = millis(); 
          startTime = oldTimeStabilisation;
          // Обнуление внутренних переменных регуляторов
          computePIDlinear(linear_bias, linear_bias, kPlinear, kIlinear, kDlinear, periodStabilisation, true);
          computePIDangle(angle_bias, angle_bias, kPangle, kIangle, kDangle, periodStabilisation, true); 
          flagPrint = 0;
          maxLinear = 0;
          maxAngle = 0;
        }
      break;
    case STABILISATION:
      stabilisation();  // Выработка управляющего воздействия
      break;
    case FALLED:
      break;
  }
  char key = pad.getKey();  // Проверка нажатия кнопки
  if(SendOPC == 1)
  {
    send_OPC(); // Обмен данными с ОРС сервером
    //  Иммитация нажатия кнопки ОРС сервером
    if(holdingRegs[11] == 1)
    {
      holdingRegs[11] = 0;
      key = '1';
    }
    if(holdingRegs[12] == 1)
    {
      holdingRegs[12] = 0;
      key = '2';
    }
    if(holdingRegs[13] == 1)
    {
      holdingRegs[13] = 0;
      key = '3';
    }
    if(holdingRegs[14] == 1)
    {
      holdingRegs[14] = 0;
      key = '4';
    }
  }
  if(key){
    handlerKey(key);  //  Обработка нажатия кнопки
  }
  
}


inline __attribute__((always_inline)) void handlerKey(char key){
  switch(State){
    case READY:
      switch(key){
          case '1': // Переключение алгоритма
            if(chooseAlgorithm == 0)
              chooseAlgorithm = 1;
            else
              chooseAlgorithm = 0;
            break;
          case '2': // Вкл/Выкл обмен данными с ОРС сервером
            if(SendOPC == 1)
              SendOPC = 0;
            else
              SendOPC = 1;
            break;
      }
      break;
    case STABILISATION:
      switch(key){
          case '1': // Обнуление максимально достигнутых параметров
            maxLinear = 0;
            maxAngle = 0;
            break;
          case '4': // Выключение СУД
            while(EncoderValue2 > (angle_bias - criticalAngle) && EncoderValue2 < (angle_bias + criticalAngle));
            State = READY;
            break;
      }
      break;
    case FALLED:
      switch(key){
          case '4': // Выход из режима аварии
            State = READY;
            break;
      }
      break;
  }
  delay(100);
  
}



inline __attribute__((always_inline)) void calibration(){
  int16_t ax, ay, az, gx, gy, gz;
  double tmpAngle = 0;
  double tmpBias = 0;
  LCD.setCursor(0, 1); // ставим курсор на 1 символ второй строки
  for(int i = 0; i < COUNT; i++)
  {
    mpu.getMotion6(&ax, &ay, &az, &gx, &gy, &gz); // Получение параметров ускорений по осям
    tmpAngle += ((double)ay)/COUNT; // Усреднение значения ускорения свободного падения
    if((i % (COUNT/16)) == 0)      
      LCD.write(255); 
  }  
  // Введение поправки в целевой угол
  tmpBias = (((3.1415/2) - acos((tmpAngle - horizontErr)/G))*8000)/(2*3.1415);
  angle_bias = EncoderValue2 + DEFAULT_BIAS - tmpBias;
  linear_bias = EncoderValue1;
  LCD.clear();
  State = READY;
}

inline __attribute__((always_inline)) void stabilisation(){
  if((EncoderValue2 > (angle_bias - criticalAngle) && EncoderValue2 < (angle_bias + criticalAngle)) && 
    (EncoderValue1 > (linear_bias - criticalLinear) && EncoderValue1 < (linear_bias + criticalLinear))){
    if(chooseAlgorithm == 0)
    { // Расчет управляющего воздействия по алгоритму 1
      linearStabAngle = computePIDlinear(EncoderValue1, linear_bias, kPlinear, kIlinear, kDlinear, periodStabilisation);
      angle = computePIDangle(EncoderValue2, angle_bias - linearStabAngle, kPangle, kIangle, kDangle, periodStabilisation); 
    }
    else
    { // Расчет управляющего воздействия по алгоритму 2
      angle = computePIDangle(EncoderValue2, angle_bias, kPangle2, kIangle2, kDangle2, periodStabilisation) - computePIDlinear(EncoderValue1, linear_bias, kPlinear2, kIlinear2, kDlinear2, periodStabilisation); 
    }
    // Выдача управляющего ШИМ сигнала
    if(angle < -MIN_POWER)
    {
      angle = -angle;
      if(angle > 1023)
        angle = 1023;
      analogWrite(MOTOR_A, (angle == 255?256:angle));
      analogWrite(MOTOR_B, LOW);
    }
    else if(angle > MIN_POWER){
      if(angle > 1023)
        angle = 1023;
      analogWrite(MOTOR_B, (angle == 255?256:angle));
      analogWrite(MOTOR_A, LOW);
    }
    else{
      analogWrite(MOTOR_A, LOW);
      analogWrite(MOTOR_B, LOW);
    }
    if(millis() - startTime > 3000)
    { // Созранение максимально достигнутых параметров отклонения
      if(abs(EncoderValue2 - angle_bias) > maxAngle)
        maxAngle = abs(EncoderValue2 - angle_bias);
      if(abs(EncoderValue1 - linear_bias) > maxLinear)
        maxLinear = abs(EncoderValue1 - linear_bias);
      if(flagPrint == 0)
      { // Если ранее текст не выводился, то вывод полного текста
        LCD.setCursor(0, 0); // ставим курсор на 1 символ первой строки
        LCD.print((2 * R * 3.1415 * (EncoderValue1 - linear_bias) / 1320)); // печатаем сообщение на первой строке
        LCD.setCursor(5, 0); // ставим курсор на 1 символ первой строки
        LCD.print(" cm max  "); // печатаем сообщение на первой строке
        LCD.setCursor(0, 1); // ставим курсор на 1 символ первой строки
        LCD.print((double)degrees(2 * 3.1415 * (EncoderValue2 - angle_bias) / 8000)); // печатаем сообщение на первой строке
        LCD.write(223); 
        LCD.setCursor(5, 1); // ставим курсор на 1 символ первой строки
        LCD.print("max  "); // печатаем сообщение на первой строке
        LCD.print("  "); // печатаем сообщение на первой строке
        flagPrint = 1;
      }
      else
      {
        if(maxLinear != prevMaxLinear)
        { // Если был изменен, то вывод нового на дисплей
          LCD.setCursor(0, 0); // ставим курсор на 1 символ первой строки
          LCD.print((2 * R * 3.1415 * (maxLinear) / 1320)); // печатаем сообщение на первой строке
          LCD.print(" cm "); // печатаем сообщение на первой строке
          prevMaxLinear = maxLinear;
        }
        if(maxAngle != prevMaxAngle)
        { // Если был изменен, то вывод нового на дисплей
          LCD.setCursor(0, 1); // ставим курсор на 1 символ первой строки
          LCD.print((double)degrees(2 * 3.1415 * (maxAngle) / 8000)); // печатаем сообщение на первой строке
          LCD.write(223); 
          LCD.setCursor(5, 1); // ставим курсор на 1 символ первой строки
          LCD.print(" max "); // печатаем сообщение на первой строке
          prevMaxAngle = maxAngle;
        }
      }
    }
  }
  else{ // Переход в состояние аварии
    analogWrite(MOTOR_A, LOW);
    analogWrite(MOTOR_B, LOW);
    if(millis() - startTime > 200)
    { // Если прошло более 0.2с после включения СУД
      LCD.clear();
      LCD.setCursor(0, 0); // ставим курсор на 1 символ первой строки
      LCD.print("Crash"); // печатаем сообщение на первой строке
      LCD.setCursor(0, 1); // ставим курсор на 1 символ первой строки
      //  Вывод на дисплей причины аварии
      if(!(EncoderValue1 > (linear_bias - criticalLinear) && EncoderValue1 < (linear_bias + criticalLinear)))
      {
        LCD.print("Pos: "); // печатаем сообщение на первой строке
        LCD.print((2 * R * 3.1415 * (EncoderValue1 - linear_bias) / 1320)); 
        LCD.print(" cm"); // печатаем сообщение на первой строке
      }
      else
      {
        LCD.print("Ang: "); // печатаем сообщение на первой строке
        LCD.print((double)degrees(2 * 3.1415 * (EncoderValue2 - angle_bias) / 8000));    
        LCD.write(223);    
      }
      State = FALLED;
    }
    else
    {
      State = READY;
    }
  }    
}

inline __attribute__((always_inline)) void send_OPC(){
  // Подготовка данных к отправке на ОРС сервер
  holdingRegs[0] = EncoderValue2;
  holdingRegs[1] = angle_bias;
  holdingRegs[2] = EncoderValue1;
  holdingRegs[3] = linear_bias;
  holdingRegs[4] = chooseAlgorithm;
  if(chooseAlgorithm == 0)
  {
    holdingRegs[5] = (int)(kPangle*1000);
    holdingRegs[6] = (int)(kIangle*1000);
    holdingRegs[7] = (int)(kDangle*1000);
    holdingRegs[8] = (int)(kPlinear*1000);
    holdingRegs[9] = (int)(kIlinear*1000);
    holdingRegs[10] = (int)(kDlinear*1000);
  }
  else
  {
    holdingRegs[5] = (int)(kPangle2*1000);
    holdingRegs[6] = (int)(kIangle2*1000);
    holdingRegs[7] = (int)(kDangle2*1000);
    holdingRegs[8] = (int)(kPlinear2*1000);
    holdingRegs[9] = (int)(kIlinear2*1000);
    holdingRegs[10] = (int)(kDlinear2*1000);
  }
  holdingRegs[11] = 0;
  holdingRegs[12] = 0;
  holdingRegs[13] = 0;
  holdingRegs[14] = 0;
  holdingRegs[15] = State;
  holdingRegs[16] = criticalAngle;
  holdingRegs[17] = criticalLinear;
  holdingRegs[18] = controlPeriod;
  holdingRegs[19] = periodStabilisation;
  holdingRegs[20] = maxAngle;
  holdingRegs[21] = maxLinear;
  holdingRegs[22] = 0;

  slave.poll( holdingRegs, HOLDING_REGS_SIZE);

  // Обработка полученных данных от ОРС сервера
  if(holdingRegs[22] == 1)
  {
    holdingRegs[22] = 0;
    slave.poll( holdingRegs, HOLDING_REGS_SIZE);
    delay(1000);
    softReset();
  }
  linear_bias = holdingRegs[3];
  if(chooseAlgorithm == 0)
  {
    kPangle = ((double)holdingRegs[5]/1000);
    kIangle = ((double)holdingRegs[6]/1000);
    kDangle = ((double)holdingRegs[7]/1000);
    kPlinear = ((double)holdingRegs[8]/1000);
    kIlinear = ((double)holdingRegs[9]/1000);
    kDlinear = ((double)holdingRegs[10]/1000);
  }
  else
  {
    kPangle2 = ((double)holdingRegs[5]/1000);
    kIangle2 = ((double)holdingRegs[6]/1000);
    kDangle2 = ((double)holdingRegs[7]/1000);
    kPlinear2 = ((double)holdingRegs[8]/1000);
    kIlinear2 = ((double)holdingRegs[9]/1000);
    kDlinear2 = ((double)holdingRegs[10]/1000);
  }
  chooseAlgorithm = holdingRegs[4];
  criticalAngle = holdingRegs[16];
  criticalLinear = holdingRegs[17];
  controlPeriod = holdingRegs[18];
}


// Функция, реализующая подчиненный регулятор
long computePIDangle(int input, int setpoint, double kp, double ki, double kd, unsigned long dt, bool restartPID) {
  static long integralAngle = 0, prevErrAngle = 0;
  if(restartPID == true)
  {
    integralAngle = 0;
    prevErrAngle = 0;
    return 0;
  }
  int err = setpoint - input;
  integralAngle += err * dt;
  double D = ((double)(err - prevErrAngle)) / dt;
  prevErrAngle = err;
  return (err * kp + ((double)integralAngle)*ki + D * kd);
}

// Функция, реализующая ведущий регулятор
long computePIDlinear(int input, int setpoint, double kp, double ki, double kd, unsigned long dt, bool restartPID) {
  static long integralLinear = 0, prevErrLinear = 0;
  if(restartPID == true)
  {
    integralLinear = 0;
    prevErrLinear = 0;
    return 0;
  }
  int err = setpoint - input;
  integralLinear += err * dt;
  double D = ((double)(err - prevErrLinear)) / dt;
  prevErrLinear = err;
  return (err * kp + ((double)integralLinear)*ki + D * kd);
}

// Расчет управляющего воздействия алгоритмом 2
int computeParallel() 
{ 
   //расчет наблюдателя
   Va[0] = (Ae[0][0] * Xa[0] + Ae[0][1] * Xa[1]) + (He[0][0] * Y[0] + He[0][1] * Y[1]) + Be[0] * U; 
   Va[1] = (Ae[1][0] * Xa[0] + Ae[1][1] * Xa[1]) + (He[1][0] * Y[0] + He[1][1] * Y[1]) + Be[1] * U; 
   //обновление первичной информации
   Y[0] = EncoderValue2; 
   Y[1] = EncoderValue1; 
   Xa[0] = H[0][0] * Y[0] + H[0][1] * Y[1]; 
   Xa[1] = H[1][0] * Y[0] + H[1][1] * Y[1]; 
   U = (int)(-S[0] * Y[0] - S[1] * Xa[0] - S[2] * Y[1] - S[3] * Xa[1]); 
   return U; 
} 
  
// Обратотка информации с ДУПК
void UpdateEncoder1() 
{ 
 int MSB = digitalRead(EncoderPinMSB1); //MSB = most significant bit 
 int LSB = digitalRead(EncoderPinLSB1); //LSB = least significant bit 
 int encoded = (MSB << 1) | LSB; //converting the 2 pin value to single number 
 int sum = (lastEncoded1 << 2) | encoded; //adding it to the previous encoded value 
 if (sum == 0b1101 || sum == 0b0100 || sum == 0b0010 || sum == 0b1011) EncoderValue1 ++; 
 if (sum == 0b1110 || sum == 0b0111 || sum == 0b0001 || sum == 0b1000) EncoderValue1 --; 
 lastEncoded1 = encoded; //store this value for next time
// AngleValue1 = (double)2 * 3.1415 * EncoderValue1 / 1320; //пересчет показаний в радианы
} 

// Обратотка информации с ДУПОУ
void UpdateEncoder2() 
{ 
 int MSB = digitalRead(EncoderPinMSB2); //MSB = most significant bit 
 int LSB = digitalRead(EncoderPinLSB2); //LSB = least significant bit 
 int encoded = (MSB << 1) | LSB; //converting the 2 pin value to single number 
 int sum = (lastEncoded2 << 2) | encoded; //adding it to the previous encoded value 
 if (sum == 0b1101 || sum == 0b0100 || sum == 0b0010 || sum == 0b1011) EncoderValue2 ++; 
 if (sum == 0b1110 || sum == 0b0111 || sum == 0b0001 || sum == 0b1000) EncoderValue2 --; 
 lastEncoded2 = encoded; //store this value for next time
// AngleValue2 = (double)2 * 3.1415 * EncoderValue2 / 8000; //пересчет показаний в радианы
} 


// Перезагрузка МК
void softReset() {
  asm volatile ("jmp 0");
}
