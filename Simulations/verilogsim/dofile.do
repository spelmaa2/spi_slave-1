add wave -position insertpoint  \
sim:/tb_inverter/A \
sim:/tb_inverter/initdone \
sim:/tb_inverter/clock \
sim:/tb_inverter/Z \

run -all
