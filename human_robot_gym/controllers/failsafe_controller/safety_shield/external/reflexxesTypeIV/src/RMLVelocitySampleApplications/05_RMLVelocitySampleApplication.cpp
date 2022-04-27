//  ---------------------- Doxygen info ----------------------
//! \file 05_RMLVelocitySampleApplication.cpp
//!
//! \brief
//! Test application number 2 for the Reflexxes Motion Libraries
//! (basic velocity-based interface, complete description of output values)
//! \n
//! \n
//! \n
//! Reflexxes GmbH\n
//! Sandknoell 7\n
//! D-24805 Hamdorf\n
//! GERMANY\n
//! \n
//! http://www.reflexxes.com\n
//!
//! \date October 2013
//! 
//! \version 1.3.2
//!
//!	\author Torsten Kroeger, <info@reflexxes.com>
//!	
//!
//! \note Copyright (C) 2013 Reflexxes GmbH.
//  ----------------------------------------------------------
//   For a convenient reading of this file's source code,
//   please use a tab width of four characters.
//  ----------------------------------------------------------


#include <stdio.h>
#include <stdlib.h>

#include <ReflexxesAPI.h>
#include <RMLVelocityFlags.h>
#include <RMLVelocityInputParameters.h>
#include <RMLVelocityOutputParameters.h>


//*************************************************************************
// defines

#define CYCLE_TIME_IN_SECONDS					0.001
#define NUMBER_OF_DOFS							3


//*************************************************************************
// Main function to run the process that contains the test application
// 
// This function contains source code to get started with the Type IV  
// Reflexxes Motion Library. Based on the program 
// 04_RMLVelocitySampleApplication.cpp, this sample code becomes extended by
// using (and describing) all available output values of the velocity-based
// algorithm. As in the former example, we compute a trajectory for a
// system with three degrees of freedom starting from an arbitrary state of
// motion. This code snippet again directly corresponds to the example 
// trajectories shown in the documentation.
//*************************************************************************
int main()
{
    // ********************************************************************
    // Variable declarations and definitions
    
    bool						FirstCycleCompleted			=	false	;
    
    int							ResultValue					=	0
							,	i							=	0
							,	j							=	0		;

    ReflexxesAPI				*RML						=	NULL	;
    
    RMLVelocityInputParameters	*IP							=	NULL	;
    
    RMLVelocityOutputParameters	*OP							=	NULL	;
    
    RMLVelocityFlags			Flags									;

    // ********************************************************************
    // Creating all relevant objects of the Type IV Reflexxes Motion Library	
    
    RML	=	new ReflexxesAPI(					NUMBER_OF_DOFS
                                            ,	CYCLE_TIME_IN_SECONDS	);
    
    IP	=	new RMLVelocityInputParameters(		NUMBER_OF_DOFS			);
    
    OP	=	new RMLVelocityOutputParameters(	NUMBER_OF_DOFS			);
    
    // ********************************************************************
    // Set-up a timer with a period of one millisecond
    // (not implemented in this example in order to keep it simple)
    // ********************************************************************	

    printf("-------------------------------------------------------\n"	);
    printf("Reflexxes Motion Libraries                             \n"	);
    printf("Example: 05_RMLVelocitySampleApplication               \n\n");
    printf("This example demonstrates the use of the entire output \n"	);
    printf("values of the velocity-based Online Trajectory         \n"	);
    printf("Generation algorithm of the Type IV Reflexxes Motion   \n"	);
    printf("Library.                                               \n\n");
    printf("Copyright (C) 2013 Reflexxes GmbH                      \n"	);
    printf("-------------------------------------------------------\n"	);

    // ********************************************************************
    // Set-up the input parameters
    
    // In this test program, arbitrary values are chosen. If executed on a
    // real robot or mechanical system, the position is read and stored in
    // an RMLVelocityInputParameters::CurrentPositionVector vector object.
    // For the very first motion after starting the controller, velocities
    // and acceleration are commonly set to zero. The desired target state
    // of motion and the motion constraints depend on the robot and the
    // current task/application.
    // The internal data structures make use of native C data types
    // (e.g., IP->CurrentPositionVector->VecData is a pointer to
    // an array of NUMBER_OF_DOFS double values), such that the Reflexxes
    // Library can be used in a universal way.	
    
    IP->CurrentPositionVector->VecData		[0]	=	-200.0		;
    IP->CurrentPositionVector->VecData		[1]	=	 100.0		;
    IP->CurrentPositionVector->VecData		[2]	=	-300.0		;
    
    IP->CurrentVelocityVector->VecData		[0]	=	-150.0		;
    IP->CurrentVelocityVector->VecData		[1]	=	 100.0		;
    IP->CurrentVelocityVector->VecData		[2]	=	  50.0		;
    
    IP->CurrentAccelerationVector->VecData	[0]	=	 350.0		;
    IP->CurrentAccelerationVector->VecData	[1]	=	-500.0		;
    IP->CurrentAccelerationVector->VecData	[2]	=	   0.0		;	
    
    IP->MaxAccelerationVector->VecData		[0]	=	 500.0		;
    IP->MaxAccelerationVector->VecData		[1]	=	 500.0		;
    IP->MaxAccelerationVector->VecData		[2]	=	1000.0		;		

    IP->MaxJerkVector->VecData				[0]	=	1000.0		;
    IP->MaxJerkVector->VecData				[1]	=	 700.0		;
    IP->MaxJerkVector->VecData				[2]	=	 500.0		;
    
    IP->TargetVelocityVector->VecData		[0]	=	 150.0		;
    IP->TargetVelocityVector->VecData		[1]	=	  75.0		;
    IP->TargetVelocityVector->VecData		[2]	=    100.0		;

    IP->SelectionVector->VecData			[0]	=	true		;
    IP->SelectionVector->VecData			[1]	=	true		;
    IP->SelectionVector->VecData			[2]	=	true		;
    
    // ********************************************************************
    // Checking the input parameters (optional)

    if (IP->CheckForValidity())
    {
        printf("Input values are valid!\n");
    }
    else
    {
        printf("Input values are INVALID!\n");
    }

    // ********************************************************************
    // Starting the control loop
    
    while (ResultValue != ReflexxesAPI::RML_FINAL_STATE_REACHED)
    {
    
        // ****************************************************************									
        // Wait for the next timer tick
        // (not implemented in this example in order to keep it simple)
        // ****************************************************************		
    
        // Calling the Reflexxes OTG algorithm
        ResultValue	=	RML->RMLVelocity(		*IP
                                            ,	OP
                                            ,	Flags		);
                                            
        if (ResultValue < 0)
        {
            printf("An error occurred (%d).\n", ResultValue	);
            printf("%s\n", OP->GetErrorString());
            break;
        }
        
        // ****************************************************************
        // The following part completely describes all output values
        // of the Reflexxes Type IV Online Trajectory Generation
        // algorithm.
        
        if (!FirstCycleCompleted)
        {
            FirstCycleCompleted	=	true;
            
            printf("-------------------------------------------------------\n");
            printf("General information:\n\n");
            
            if (OP->IsTrajectoryPhaseSynchronized())
            {
                printf("The current trajectory is phase-synchronized.\n");
                printf("The synchronization time of the current trajectory is %.3lf seconds.\n", OP->GetSynchronizationTime());
            }
            
            if (OP->WasACompleteComputationPerformedDuringTheLastCycle())
            {
                printf("The trajectory was computed during the last computation cycle.\n");
            }
            else
            {
                printf("The input values did not change, and a new computation of the trajectory parameters was not required.\n");
            }
			if (OP->IsTheOverrideFilterActive())
			{
				printf("The override filter is active, and the desired override value has NOT been reached.\n");
				printf("The currently applied override value is %10.3lf.\n", OP->CurrentOverrideValue);
			}
			else
			{
				printf("The override filter is NOT active, and the desired override value has been reached.\n");
			}             
            
            for ( j = 0; j < NUMBER_OF_DOFS; j++)
            {
                printf("The degree of freedom with the index %d will reach its target velocity at position %.3lf after %.3lf seconds.\n"
                            ,	j
                            ,	OP->PositionValuesAtTargetVelocity->VecData[j]
                            ,	OP->ExecutionTimes->VecData[j]					);
            }			
            
            printf("The degree of freedom with the index %d will require the greatest execution time.\n", OP->GetDOFWithTheGreatestExecutionTime());			
            
            printf("-------------------------------------------------------\n");
            printf("New state of motion:\n\n");
                    
            printf("New position/pose vector                  : ");
            for ( j = 0; j < NUMBER_OF_DOFS; j++)
            {
                printf("%10.3lf ", OP->NewPositionVector->VecData[j]);
            }
            printf("\n");
            printf("New velocity vector                       : ");
            for ( j = 0; j < NUMBER_OF_DOFS; j++)
            {
                printf("%10.3lf ", OP->NewVelocityVector->VecData[j]);
            }
            printf("\n");			
            printf("New acceleration vector                   : ");
            for ( j = 0; j < NUMBER_OF_DOFS; j++)
            {
                printf("%10.3lf ", OP->NewAccelerationVector->VecData[j]);
            }
            printf("\n");
            printf("-------------------------------------------------------\n");
            printf("Extremes of the current trajectory:\n");
            
            for ( i = 0; i < NUMBER_OF_DOFS; i++)
            {
                printf("\n");
                printf("Degree of freedom                         : %d\n", i);
                printf("Minimum position                          : %10.3lf\n", OP->MinPosExtremaPositionVectorOnly->VecData[i]);
                printf("Time, at which the minimum will be reached: %10.3lf\n", OP->MinExtremaTimesVector->VecData[i]);
                printf("Position/pose vector at this time         : ");
                for ( j = 0; j < NUMBER_OF_DOFS; j++)
                {
                    printf("%10.3lf ", OP->MinPosExtremaPositionVectorArray[i]->VecData[j]);
                }
                printf("\n");
                printf("Velocity vector at this time              : ");
                for ( j = 0; j < NUMBER_OF_DOFS; j++)
                {
                    printf("%10.3lf ", OP->MinPosExtremaVelocityVectorArray[i]->VecData[j]);
                }
                printf("\n");
                printf("Acceleration vector at this time          : ");
                for ( j = 0; j < NUMBER_OF_DOFS; j++)
                {
                    printf("%10.3lf ", OP->MinPosExtremaAccelerationVectorArray[i]->VecData[j]);
                }
                printf("\n");
                printf("Maximum position                          : %10.3lf\n", OP->MaxPosExtremaPositionVectorOnly->VecData[i]);
                printf("Time, at which the maximum will be reached: %10.3lf\n", OP->MaxExtremaTimesVector->VecData[i]);
                printf("Position/pose vector at this time         : ");
                for ( j = 0; j < NUMBER_OF_DOFS; j++)
                {
                    printf("%10.3lf ", OP->MaxPosExtremaPositionVectorArray[i]->VecData[j]);
                }
                printf("\n");
                printf("Velocity vector at this time              : ");
                for ( j = 0; j < NUMBER_OF_DOFS; j++)
                {
                    printf("%10.3lf ", OP->MaxPosExtremaVelocityVectorArray[i]->VecData[j]);
                }
                printf("\n");
                printf("Acceleration vector at this time          : ");
                for ( j = 0; j < NUMBER_OF_DOFS; j++)
                {
                    printf("%10.3lf ", OP->MaxPosExtremaAccelerationVectorArray[i]->VecData[j]);
                }
                printf("\n");					
            }
            printf("-------------------------------------------------------\n");
			printf("Polynomial coefficients:\n");
            for ( i = 0; i < NUMBER_OF_DOFS; i++)
            {
                printf("\n");
                printf("Degree of freedom                         : %d\n", i);
                printf("Number of polynomial segments             : %d\n", OP->Polynomials->NumberOfCurrentlyValidSegments[i]);
				for ( j = 0; j < OP->Polynomials->NumberOfCurrentlyValidSegments[i]; j++)
				{
					OP->Polynomials->Coefficients[i][j].Echo();
				}
			}
			printf("-------------------------------------------------------\n");
        }
        // ****************************************************************

        // ****************************************************************
        // Feed the output values of the current control cycle back to 
        // input values of the next control cycle
        
        *IP->CurrentPositionVector		=	*OP->NewPositionVector		;
        *IP->CurrentVelocityVector		=	*OP->NewVelocityVector		;
        *IP->CurrentAccelerationVector	=	*OP->NewAccelerationVector	;
    }

    // ********************************************************************
    // Deleting the objects of the Reflexxes Motion Library end terminating
    // the process
    
    delete	RML			;
    delete	IP			;
    delete	OP			;

    exit(EXIT_SUCCESS)	;
}