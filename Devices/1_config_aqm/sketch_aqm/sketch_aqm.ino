//Имитирует работу датчика параметров микроклимата в помещении
//Автор: Безняков Павел Михайлович
//Информация по протоколу modbus
//Статья Arduino® & Modbus Protocol
//https://docs.arduino.cc/learn/communication/modbus#introduction
//Библиотека
//Modbus-Master-Slave-for-Arduino

#include <ModbusRtu.h>
#define ADDRESS 100
#define REGS_SIZE 18
uint16_t regs[REGS_SIZE];
Modbus slave(ADDRESS, 0, 0);

void setup(){
  slave.begin(9600);
  regs[0]=1000; // CO2 value = 1000
  regs[1]=200; // TVOC value = 2.00
  regs[2]=3; // PM1.0 value = 
  regs[3]=4; // PM2.5 value
  regs[4]=5; // PM10 value
  regs[5]=-600; // Temperature value
  //bitWrite(regs[5], 15, 1); //sign of temperature value
  regs[6]=700; // Humidity value
  regs[16]=2; // LCD Backlight state
  bitWrite(regs[17], 0, 1); // Mute state (0: unmute, 1: mute)
  bitWrite(regs[17], 1, 0); // Temperasture unit (0: Celsius, 1: Fahrenheit)

}
void loop(){
  slave.poll(regs, REGS_SIZE);
}

