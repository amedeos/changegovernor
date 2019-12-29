import sensors

sensors.init()
try:
    for chip in sensors.iter_detected_chips():
        print( chip,  chip.adapter_name)
        for feature in chip:
            #print(feature.label + ": " + feature.get_value())
            #print(feature.label)
            try:
                print(feature.label, feature.get_value())
            except:
                print(feature.label)
                continue
finally:
    sensors.cleanup()
