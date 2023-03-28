# odrive

## Troubleshooting
### Hanging
* If you have provided a serial number, make sure it is the correct serial number. Odrives have **2 serial numbers**: one that will be printed out when you start `odrivetool`, and one that can be accessed in `odrivetool` by running `odrv0.serial_number`. The **correct** serial number is the one that is printed out when you start `odrivetool`.
* If you have not provided a serial number, you are likely connected to the odrive elsewhere. Make sure any connections via python, `odrivetool` or the GUI are closed.


