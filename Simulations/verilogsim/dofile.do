add wave -position insertpoint  \
sim/:tb_spi_slave:clock \
sim/:tb_spi_slave:reset \
sim/:tb_spi_slave:io_mosi \
sim/:tb_spi_slave:io_cs \
sim/:tb_spi_slave:io_sclk \
sim/:tb_spi_slave:io_monitor_in \
sim/:tb_spi_slave:initdone \
sim/:tb_spi_slave:io_miso \
sim/:tb_spi_slave:io_config_out

run -all
