#include <ModbusRtu.h>
#include <SimpleKeypad.h>
#include <LCD_1602_RUS.h>
#include <MPU6050.h>
#include <LiquidCrystal_I2C.h>
#include <Wire.h>
#include <I2Cdev.h>

#define ID 1
#define HOLDING_REGS_SIZE 23
Modbus slave(ID, 0, 0);
uint16_t state = 0;
uint16_t holdingRegs[HOLDING_REGS_SIZE];

void setup(){
  int a=1;
  slave.begin(115200);
  slave.poll(holdingRegs, HOLDING_REGS_SIZE);
}
void loop(){
}

