#include <math.h>
#include <Servo.h>
#include <ModbusRtu.h>
//#include <Keypad.h>
#include <SimpleKeypad.h>
#include <LCD_1602_RUS.h>
#include <MPU6050.h>
#include <LiquidCrystal_I2C.h>
#include <Wire.h>
#include <I2Cdev.h>

// Инициализация параметров управления
#define DEFAULT_CONTROL_PERIOD 10 // Период цикла управления по умолчанию
int controlPeriod = DEFAULT_CONTROL_PERIOD; // Переменная указывающая требуемый цикл управления
unsigned long oldTimeStabilisation = 0; // Время начала предыдущего цикла управления
unsigned long periodStabilisation = 0;  // Действительное значение цикла управления
unsigned long oldMenuTime = 0;  // Время нахождения макета неподвижно
unsigned long start_time = 0;  // Время запуска СУД
long control_value = 0; // значение управляющего воздействия для алгоритма 1
long linearStabAngle = 0; // значение управляющего воздействия для алгоритма 2
int index_pid = 1; // Код выбранного набора ПИД коэффициентов (0 - внешний набор из контроллера эксперимента)/ Максимум - N_PIDS
boolean is_local_mode=true; // признак локального управления, иначе - дистанционное
#define N_PIDS 5 //количество наборов коэффициентов ПИД  регулятора
int decimals_pids[6]={0,  3,  1, 2, 0, 0}; // размер десятичной части коэффициентов ПИД регулятора
// коэффициенты ПИД регулятора в последовательности {kPangle, kIangle, kDangle, kPlinear, kIlinear, kDlinear}
double values_pids[N_PIDS][6]={{0, 0, 0, 0, 0, 0},
                              {5, 15,  35, 1, 0,  8},
                              {5, 15,  35,  3,  0,  8},
                              {5, 15,  35,  5,  0,  8},
                              {7, 15,  35,  3,  0,  8}}; 
//
// Инициализация физических параметров установки
#define R 3.17  // Радиус колеса
//
// Инициализация системы вертикализации
#define PIN_SERVO_LEFT 53
#define PIN_SERVO_RIGHT 51
Servo servo_left;// создадим объект сервопривода
Servo servo_right;
int servo_init_left=0; // начальная позиция
int servo_init_right=180; // начальная позиция
int Ang; // значение текущего угла сервопривода
int dAng=0; // значение приращения угла вертикализации (+1 или -1)
//
// Инициализация портов управления двигателями
#define MOTOR_A 6
#define MOTOR_B 7
#define MIN_POWER 70  // Минимальное управляющее воздействие, которое подается на двигатели
//                          
// инициализация акселерометра горизонтирования (уровня)
#define G 16384 // Ускорение свободного падения для акселерометра при диапазоне +-2g
#define horizontErr (-10) // Калибровочная поправка аксилирометра было 97
#define COUNT 5000  // Количество значений для горизонтирования
MPU6050 mpu;  // Объект для работы с акселерометром
double tmpBias = 0; // значение поправки целевого угла по результатам калибровки
//
// Инициализация клавиатуры
#define KP_ROWS 1 // размеры клавиатуры
#define KP_COLS 4 // размеры клавиатуры
byte colPins[KP_COLS] = {39, 37,  33, 41}; // Порты подключения к клавиатуре
byte rowPins[KP_ROWS] = {35}; // GND для клавиатуры
char keys[KP_ROWS][KP_COLS] = {{'1', '2', '3', '4'}}; // Массив имён кнопок
SimpleKeypad pad((char*)keys, rowPins, colPins, KP_ROWS, KP_COLS);  // Объект для работы с клавиатурой
//
// Инициализация modbus шины
#define HOLDING_REGS_SIZE 20 // Количество каналов для OPC сервера
#define ID   1      // Адрес МК для обмена данными с ОРС сервером
Modbus slave(ID, 0, 0);  // Объект для работы с ОРС сервером
int8_t state = 0; // Системная переменная состояния для работы с ОРС сервером
int SendOPC = 0;  // Признак режима с подключением к ОРС серверу
uint16_t holdingRegs[HOLDING_REGS_SIZE]; // Массив тегов
// указатели на регистры
uint16_t *p_angle=holdingRegs;
uint16_t *p_angle_speed=holdingRegs+1;
uint16_t *p_position=holdingRegs+2;
uint16_t *p_position_speed=holdingRegs+3;
uint16_t *p_control_value=holdingRegs+4;  
uint16_t *p_is_local_mode=holdingRegs+5; 
uint16_t *p_is_claim_received=holdingRegs+6;
uint16_t *p_initial_flag=holdingRegs+7;
uint16_t *p_index_pid=holdingRegs+8;
uint16_t *p_duration_time=holdingRegs+9;

//
// инициализация датчика линейного положения объекта
int EncoderPinMSB1 = 2; //пин датчика углового положение колеса //MSB = most significant bit
int EncoderPinLSB1 = 3; //пин датчика углового положение колеса //LSB = least significant bit  
volatile int lastEncoded1 = 0;
volatile int EncoderValue1 = 0; // начальное значение показания энкодера датчика углового положение колеса (имп)
volatile int prevEncoderValue1 = 0; // предыдущее значение показания энкодера датчика углового положение колеса (имп)
volatile double AngleValue1 = 0; // значение показания энкодера датчика углового положение колеса (гр)
int criticalLinear = 1313; // Критическое линейное смещение по умолчанию соответствует 20 см.
int linear_bias = 0;  // Целевое линейное положение
int linear_err_limit; // Допустимое значение линейного отклонения перед вертикализацией
int linear_err; // Текущая ошибка линейного отклонения перед вертикализацией
//
// инициализация датчика углового положения объекта
int EncoderPinMSB2 = 19; //пин датчика углового положение ОУ //MSB = most significant bit
int EncoderPinLSB2 = 18; //пин датчика углового положение ОУ //LSB = least significant bit  
volatile int lastEncoded2 = 0; 
volatile int EncoderValue2 = 0; // значение показания энкодера датчика углового положение ОУ (имп)
volatile int prevEncoderValue2 = 0; // предыдущее значение показания инкодера датчика углового положение ОУ (имп)
volatile double AngleValue2 = 0; // значение показания энкодера датчика углового положение ОУ (гр)
int criticalAngle = 150;  // Критическое угловое отклонение по умолчанию соответствует 6.75 гр.
#define DEFAULT_BIAS 1949 // Целевое значение углового положения относительно платформы
int angle_bias = DEFAULT_BIAS;  // Целевое угловое положение
//
// Инициализация LCD дисплея
LCD_1602_RUS LCD(0x27, 16, 2);  // Объект для вывода информации на дисплей
int flagPrint = 0;  // Признак вывода основого текста при включенной СУД на дисплей
int maxLinear = 0;  // Максимально достигнутое смещение для отображения
int maxAngle = 0;  // Максимально достигнутое угловое отклонение для отображения 
int prevMaxLinear = 0;  // Предыдущее максимально достигнутое смещение для отображения
int prevMaxAngle = 0;  // Предыдущее максимально достигнутое угловое отклонение для отображения
//
// Инициализация ПИД коэффициентов
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
//

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

enum{ // Режимы установки
  CALIBRATION, READY, STABILISATION, FALLED
} State;

enum{ // Состояния диодов
  RYG, RXX, XYX, XXG, XXX
} DiodeState;

enum{ // Режим отображения дисплея
  OPTIONS, MENU, MAXVALUES
} DisplayMode;


long computePIDangle(int input, int setpoint, double kp, double ki, double kd, unsigned long dt, bool restartPID = false);
long computePIDlinear(int input, int setpoint, double kp, double ki, double kd, unsigned long dt, bool restartPID = false);

void setup() {
  
  TCCR4A = 0b00000011;  // Переключение ШИМ в разрешение 10 бит
  
  // перевод системы вертикализации в начальное состояние
  pinMode(PIN_SERVO_LEFT, OUTPUT);
  pinMode(PIN_SERVO_RIGHT, OUTPUT);
  digitalWrite(PIN_SERVO_LEFT,LOW);
  digitalWrite(PIN_SERVO_RIGHT,LOW);
  servo_left.attach(PIN_SERVO_LEFT);
  servo_right.attach(PIN_SERVO_RIGHT);
  servo_left.write(servo_init_left);
  servo_right.write(servo_init_right);
    
  // инициализация пинов диодов
  pinMode(47, OUTPUT); // желтый диод
  pinMode(45, OUTPUT); // зеленый диод
  pinMode(43, OUTPUT); // красный диод
  
  // проверка отсветки диодов
  SetDiodColor(RYG);
  
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
  
  // Инициализация массива регистров
  *p_is_local_mode = 1; 
  *p_is_claim_received=1;
  *p_initial_flag=0;
  *p_index_pid=3;
  *p_duration_time=5;
  
  slave.begin(9600);
  //slave.poll( holdingRegs, HOLDING_REGS_SIZE);  
  
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
  LCD.print("Leveling ...");
  calibration();  // Запуск функции горизонтирования
  SetDiodColor(XXX);
  LCD.clear();
  LCD.setCursor(0, 0);
  LCD.print("Leveling done!");
  
  
  // Ожидание определения наклона объекта и корректировка целевого угла
  boolean isNotDirect=true;
  while(isNotDirect)
  {
    if((EncoderValue2 < -50))
    {
      angle_bias = tmpBias + DEFAULT_BIAS - 3894; // поправка при правой калибровке
      isNotDirect=false;    
    }
    if((EncoderValue2 > 50))
    {  
      angle_bias = tmpBias + DEFAULT_BIAS + 25; // поправка при левой калибровке
      isNotDirect=false;
    }
  }
  oldTimeStabilisation = millis();
  
  State = FALLED;
   
}

void loop() {
  //  Обработка нажатия кнопки
  char key = pad.getKey();  // Проверка нажатия кнопки
  if(key) { 
    handlerKey(key);
  }
  do{ // Пока время, прошедшее с начала цикла меньше, чем период цикла управления
    periodStabilisation = millis()-oldTimeStabilisation;
    
  }while(periodStabilisation < controlPeriod);
  oldTimeStabilisation = millis();
  
  
  
  switch(State){
    case READY: // Ожидание
        
                                       
        SetDisplayMessage(OPTIONS);
               
        // работа системы линенйного приведения
        linear_err_limit=100;
        linear_err=EncoderValue1-linear_bias;
        if (linear_err>linear_err_limit)
        {
          analogWrite(MOTOR_A, 100);
          analogWrite(MOTOR_B, LOW);
        }
        if (linear_err<-linear_err_limit)
        {
          analogWrite(MOTOR_A, LOW);
          analogWrite(MOTOR_B, 100);
        }
        if (linear_err<linear_err_limit && linear_err>-linear_err_limit)
        {
          analogWrite(MOTOR_A, LOW);
          analogWrite(MOTOR_B, LOW);
        }
                      
        // работа системы вертикализации
        if (linear_err<linear_err_limit && linear_err>-linear_err_limit)
        {
          Ang=Ang+dAng;
          if (dAng>0)
          {
            servo_left.write(Ang);
          }
          if (dAng<0)
          {
            servo_right.write(Ang);
          } 
        }       
        
        // проверка факта вертикализации и переход в режим стабилизации
        if((EncoderValue2 >= angle_bias - 15) && (EncoderValue2 <= angle_bias + 15))
        { // Переход в состояние стабилизации
          State = STABILISATION;
                    
          servo_left.write(servo_init_left);
          servo_right.write(servo_init_right);
          
          SetDisplayMessage(MENU);
                  
          start_time = millis();
          
          // Обнуление внутренних переменных регуляторов
          computePIDlinear(linear_bias, linear_bias, kPlinear, kIlinear, kDlinear, periodStabilisation, true);
          computePIDangle(angle_bias, angle_bias, kPangle, kIangle, kDangle, periodStabilisation, true); 
          flagPrint = 0;
          maxLinear = 0;
          maxAngle = 0;
        }
      break;
    
    case STABILISATION:
      // TO DO
      
      SetDiodColor(XXG);
      stabilisation();  // Выработка управляющего воздействия
      break;
   
    case FALLED:
      SetDiodColor(XXX);
      // выбор сервопривода вертикализации
      if(EncoderValue2 > angle_bias)
        {
          Ang=servo_init_right;
          dAng=-1;
     
        }
      if(EncoderValue2 < angle_bias)
        {
          Ang=servo_init_left;
          dAng=1;
        }
      // выключение моторов
      analogWrite(MOTOR_A, LOW);
      analogWrite(MOTOR_B, LOW);
            
      // печать текущих параметров объекта 
      if(((prevEncoderValue1 >= EncoderValue1 + 10) || (prevEncoderValue1 <= EncoderValue1 - 10)) || ((prevEncoderValue2 >= EncoderValue2 + 10) || (prevEncoderValue2 <= EncoderValue2 - 10)))
        { // Параметры углового или линейного положения были изменены
          prevEncoderValue2 = EncoderValue2;
          prevEncoderValue1 = EncoderValue1;
          oldMenuTime = millis();
        }

      if(millis() - oldMenuTime < 3000)
          // Вывод параметров углового или линейного положения
          SetDisplayMessage(OPTIONS);  
      else
         // Вывод меню
        SetDisplayMessage(MENU);
        
      if (is_local_mode==false)
        {
         slave.poll(holdingRegs, HOLDING_REGS_SIZE);
         if (*p_is_claim_received==true)
          {
            index_pid=*p_index_pid;
            SetStateReady();
            *p_is_claim_received=false;
            
          }
          
      }
        
        
        
        
        
        break;
  }
}


inline __attribute__((always_inline)) void handlerKey(char key){
  switch(State){
    case READY:
      switch(key){
          case '2': // Переключение алгоритма
            break;
          case '3': // Вкл/Выкл обмен данными с ОРС сервером
            break;
          case '4': // Выключение СУД
            //while(EncoderValue2 > (angle_bias - criticalAngle) && EncoderValue2 < (angle_bias + criticalAngle));
            servo_left.write(servo_init_left);
            servo_right.write(servo_init_right);
            State = FALLED;
            break;
      }
      break;
    case STABILISATION:
      switch(key){
          case '1': // Обнуление максимально достигнутых параметров
            maxLinear = 0;
            maxAngle = 0;
            break;
          case '3': // изменение режима управления: local/remote
            if (is_local_mode) is_local_mode=false;
            else is_local_mode=true;
            SetDisplayMessage(MENU);
            break;
          case '4': // Выключение СУД
            //while(EncoderValue2 > (angle_bias - criticalAngle) && EncoderValue2 < (angle_bias + criticalAngle));
            State = FALLED;
            break;
      }
      break;
    case FALLED:
      switch(key){
        case '2': // Переключение набора коэффициентов ПИД регулятора
            index_pid+=1;
            index_pid%=N_PIDS;
            break;
        case '3': // изменение режима управления: local/remote
            if (is_local_mode) is_local_mode=false;
            else is_local_mode=true;
            break;  
        case '4': // Переход в режим подготовки к стабилизации
            SetStateReady();
            break;
      }
      break;
  }
  delay(100);
  
}



inline __attribute__((always_inline)) void calibration(){
  int16_t ax, ay, az, gx, gy, gz;
  double tmpAngle = 0;
  
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
  //angle_bias = EncoderValue2 + DEFAULT_BIAS - tmpBias;
  linear_bias = EncoderValue1;
  
}

inline __attribute__((always_inline)) void stabilisation()
{
  if((EncoderValue2 > (angle_bias - criticalAngle) && EncoderValue2 < (angle_bias + criticalAngle)) && 
    (EncoderValue1 > (linear_bias - criticalLinear) && EncoderValue1 < (linear_bias + criticalLinear)))
  {
    
      // Расчет управляющего воздействия по алгоритму
    linearStabAngle = computePIDlinear(EncoderValue1, linear_bias, kPlinear, kIlinear, kDlinear, periodStabilisation);
    control_value = computePIDangle(EncoderValue2, angle_bias - linearStabAngle, kPangle, kIangle, kDangle, periodStabilisation); 
        
    // Выдача управляющего ШИМ сигнала
    if(control_value < -MIN_POWER)
    {
      control_value = -control_value;
      if(control_value > 1023)
        control_value = 1023;
      analogWrite(MOTOR_A, (control_value == 255?256:control_value));
      analogWrite(MOTOR_B, LOW);
    }
    else if(control_value > MIN_POWER)
    {
      if(control_value > 1023)
        control_value = 1023;
      analogWrite(MOTOR_B, (control_value == 255?256:control_value));
      analogWrite(MOTOR_A, LOW);
    }
    else
    {
      analogWrite(MOTOR_A, LOW);
      analogWrite(MOTOR_B, LOW);
    }
    // Созранение максимально достигнутых параметров отклонения
    if(abs(EncoderValue2 - angle_bias) > maxAngle)
        maxAngle = abs(EncoderValue2 - angle_bias);
    if(abs(EncoderValue1 - linear_bias) > maxLinear)
        maxLinear = abs(EncoderValue1 - linear_bias);
    if(maxLinear != prevMaxLinear || maxAngle != prevMaxAngle)
    {
        //SetDisplayMessage(MAXVALUES);
        //LCD монитор тормозит цикл управления             
        prevMaxLinear = maxLinear;
        prevMaxAngle = maxAngle;
    }
  }

  
  else
  { // Переход в состояние аварии
    analogWrite(MOTOR_A, LOW);
    analogWrite(MOTOR_B, LOW);
    if(millis() - start_time > 200)
    { // Если прошло более 0.2с после включения СУД
      LCD.clear();
      LCD.setCursor(0, 0); // ставим курсор на 1 символ первой строки
      LCD.print("Crash"); // печатаем сообщение на первой строке
      LCD.setCursor(0, 1); // ставим курсор на 1 символ первой строки
      //  Вывод на дисплей причины аварии
      if(!(EncoderValue1 > (linear_bias - criticalLinear) && EncoderValue1 < (linear_bias + criticalLinear)))
      {
        LCD.print("Pos* "); // печатаем сообщение на первой строке
        LCD.print((2 * R * 3.1415 * (EncoderValue1 - linear_bias) / 1320)); 
        LCD.print(" cm"); // печатаем сообщение на первой строке
      }
      else
      {
        LCD.print("Ang* "); // печатаем сообщение на первой строке
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
  holdingRegs[4] = index_pid;
  if(index_pid == 0)
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

  slave.poll(holdingRegs, HOLDING_REGS_SIZE);

  // Обработка полученных данных от ОРС сервера
  if(holdingRegs[22] == 1)
  {
    holdingRegs[22] = 0;
    slave.poll( holdingRegs, HOLDING_REGS_SIZE);
    delay(1000);
    softReset();
  }
  linear_bias = holdingRegs[3];
  if(index_pid == 0)
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
  index_pid = holdingRegs[4];
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

// отображение на дисплее параметров объекта
void SetDisplayMessage(int message)
{
  switch (message)
  {
    case OPTIONS:
      LCD.setCursor(0, 0); // ставим курсор на 1 символ первой строки
      LCD.print("Pos: "); // печатаем сообщение на первой строке
      LCD.print((2 * R * 3.1415 * (EncoderValue1 - linear_bias) / 1320)); // печатаем сообщение на первой строке
      LCD.print(" cm    "); // печатаем сообщение на первой строке
      LCD.setCursor(0, 1); // ставим курсор на 1 символ первой строки
      LCD.print("Ang: "); // печатаем сообщение на первой строке
      LCD.print((double)degrees(2 * 3.1415 * (EncoderValue2 - angle_bias) / 8000)); // печатаем сообщение на первой строке
      LCD.write(223); 
      LCD.print("     "); // печатаем сообщение на первой строке
      break;
    case MENU:
      LCD.setCursor(0, 1); // ставим курсор на 1 символ второй строки
      LCD.print("Mod('3'): "); 
      if(is_local_mode == true)
        LCD.print("local "); // печатаем сообщение на первой строке
      else
        LCD.print("remote "); // печатаем сообщение на первой строке
      if (State==FALLED){
        LCD.setCursor(0, 0); // ставим курсор на 1 символ первой строки
        LCD.print("Alg('2'):       ");
        LCD.setCursor(10, 0);
        LCD.print(index_pid); // печатаем сообщение на первой строке
      }
      if (State==STABILISATION){
        LCD.setCursor(0, 0); // ставим курсор на 1 символ первой строки
        LCD.print("   CSU is on   "); // печатаем сообщение на первой строке
      }
      break;
    case MAXVALUES:
       LCD.setCursor(0, 0); // ставим курсор на 1 символ первой строки
       LCD.print("L");
       LCD.print("|Max(cm):");
       LCD.print((2 * R * 3.1415 * (maxLinear) / 1320)); // печатаем сообщение на первой строке
       LCD.print("  ");
       LCD.setCursor(0, 1); // ставим курсор на 1 символ первой строки
       LCD.print("M");
       LCD.print("|Max( ");
       LCD.write(223);
       LCD.print("):");
       LCD.print((double)degrees(2 * 3.1415 * (maxAngle) / 8000)); // печатаем сообщение на первой строке
       LCD.print("  "); // печатаем сообщение на первой строке
       break;
  }
}


// Установка заданной комбинации отсветки светодиодов
void SetDiodColor(int diode)
{
  switch (diode)
  {
    case RYG: // горят красный, желтый, зеленый
      digitalWrite(43, HIGH);
      digitalWrite(47, HIGH);
      digitalWrite(45, HIGH);
      break;
    case RXX: // горит красный
      digitalWrite(43, HIGH);
      digitalWrite(47, LOW);
      digitalWrite(45, LOW);
    break;
    case XYX: // горит желтый
      digitalWrite(43, LOW);
      digitalWrite(47, HIGH);
      digitalWrite(45, LOW);
    break;
    case XXG: // горит зеленый
      digitalWrite(43, LOW);
      digitalWrite(47, LOW);
      digitalWrite(45, HIGH);
    break;
    case XXX: // ничего не горит
      digitalWrite(43, LOW);
      digitalWrite(47, LOW);
      digitalWrite(45, LOW);
    break;
  }
}

void SetStateReady()
// подготовка к переходу в состояние READY
{
  State = READY;
  SetDiodColor(RXX);
  // выбор и подготовка коэффициентов ПИД регулятора
  kPangle=values_pids[index_pid][0]/pow(10,decimals_pids[0]);
  kIangle=values_pids[index_pid][1]/pow(10,decimals_pids[1]);
  kDangle=values_pids[index_pid][2]/pow(10,decimals_pids[2]);
  kPlinear=values_pids[index_pid][3]/pow(10,decimals_pids[3]);
  kIlinear=values_pids[index_pid][4]/pow(10,decimals_pids[4]);
  kDlinear=values_pids[index_pid][5]/pow(10,decimals_pids[5]);
}


// Перезагрузка МК
void softReset() {
  asm volatile ("jmp 0");
}
