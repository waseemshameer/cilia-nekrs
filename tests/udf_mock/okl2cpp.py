import re, sys
s = open(sys.argv[1]).read()
s = s.replace('#include "udf.hpp"', '#include "mock.hpp"')
s = re.sub(r';\s*@(outer|inner)\(\d\)\)', ')', s)
s = s.replace('@kernel ', '').replace('@restrict', '').replace('@shared', '').replace('@barrier();', '')
s = s.replace('#ifdef __okl__', '#if 1')
open(sys.argv[2], 'w').write(s)
