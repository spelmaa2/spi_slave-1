add wave -position insertpoint  \
sim:/tb_spi/A \
sim:/tb_spi/initdone \
sim:/tb_spi/clock \
sim:/tb_spi/Z \

run -all
