



































#ifndef ScCRI
#define ScCRI
#include <RMLVelocityInputParameters.h>
#include <RMLVelocityOutputParameters.h>
#include <RMLVector.h>
#include <TypeIVRMLPolynomial.h>
#include <TypeIVRMLDefinitions.h>
#include <TypeIVRMLMovingAverageFilter.h>
#include <RMLVelocityFlags.h>
#include <stdlib.h>
using namespace qPN_6;






































class TypeIVRMLVelocity{public:



























TypeIVRMLVelocity(const unsigned int&ggmbr,const double&nsANK,const bool&kjOCK=
false,const double&cnY6I=qIT2N);





~TypeIVRMLVelocity(void);












































































int Yq2Ls(const RMLVelocityInputParameters&zqVEb,RMLVelocityOutputParameters*
SDTKM,const RMLVelocityFlags&Jdf48);























































int Xvpsd(const double&PxS7M,RMLVelocityOutputParameters*SDTKM);








int SetupOverrideFilter(const double&_IGXH,const double&kNQ3O);protected:





enum CYw8l{
omT9P=false,
T3CdJ=true};





















































void Q48EP(const RMLVelocityInputParameters&zqVEb,RMLVelocityOutputParameters*
SDTKM);





















void kJlKk(void);




















void GuUm1(void);





















void lzEiV(void);

























void VfImR(void);








































int Y07KE(const double&PxS7M,const double&OverrideValue,
RMLVelocityOutputParameters*tg6GG)const;
















































bool tHCRc(void);























































void RQuk0(const double&PxS7M,const double&OverrideValue,
RMLVelocityOutputParameters*tg6GG)const;

















































bool q9K7w(const RMLVelocityInputParameters&zqVEb,RMLVelocityOutputParameters*
SDTKM);








































void chwJj(RMLVelocityOutputParameters*tg6GG)const;



























void OOJL1(void);
















void TTtbr(void);










bool F2ivR;









bool kj2Tc;







bool xheaR;











bool sg_1Y;









bool X0n_9;








int ReturnValue;







unsigned int NumberOfDOFs;







unsigned int YDfwn;







double CycleTime;








double SynchronizationTime;









double zzKJk;













double Ghz_l;













double z2xUW;












double MaxTimeForOverrideFilter;














RMLVelocityFlags onYRt;












RMLBoolVector*Ge1KL;












RMLBoolVector*qeRBJ;













RMLBoolVector*Cc2Sm;









RMLIntVector*ATtzi;








RMLDoubleVector*ExecutionTimes;









RMLDoubleVector*HxNxN;









RMLDoubleVector*BNvJP;









RMLDoubleVector*VmKWV;









RMLDoubleVector*o04Be;










RMLDoubleVector*CrzAq;










RMLDoubleVector*TH6RH;








RMLDoubleVector*Pa6wf;





RMLDoubleVector*NkYww;















RMLVelocityInputParameters*xObJM;









RMLVelocityInputParameters*_DBry;










RMLVelocityInputParameters*KZs7z;













RMLVelocityOutputParameters*gSTLu;











RMLVelocityOutputParameters*_fSN4;













TypeIVRMLVelocity*z1jCu;











XkwFr*Polynomials;












Dt6QZ*E24br;};
#endif

