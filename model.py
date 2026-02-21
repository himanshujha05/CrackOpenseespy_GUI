import openseespy.opensees as ops

ops.wipe()
ops.model('basic', '-ndm', 2, '-ndf', 2)

ops.node(1, 0.0, 0.0)
ops.node(2, 1.0, 0.0)

ops.fix(1, 1, 1)
ops.fix(2, 0, 1)

ops.uniaxialMaterial("Elastic", 1, 3000.0)
ops.element("truss", 1, 1, 2, 1.0, 1)

print("✅ OpenSeesPy OK:", ops.pyversion())
