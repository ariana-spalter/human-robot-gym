// -*- lsst-c++ -*/
/**
 * @file safety_shield.h
 * @brief Defines the online verification class
 * @version 0.1
 * @copyright MIT License. Please see package.xml for further detail.
 */

#include <cmath>
#include <math.h>
#include <algorithm>
#include <vector>
#include <time.h>
#include <stdio.h>

#include "reach_lib.hpp"

#include "safety_shield/long_term_traj.h"
#include "safety_shield/path.h"
#include "safety_shield/motion.h"
#include "safety_shield/robot_reach.h"
//#include "safety_shield/human_reach.h"
#include "safety_shield/verify.h"
#include "safety_shield/verify_iso.h"
//#include "safety_shield/advanced_verify_iso.h"
//#include "safety_shield/control_command_translator.h"
//#include "safety_shield/rviz_marker.h"

#include "ReflexxesAPI.h"
#include "RMLPositionFlags.h"
#include "RMLPositionInputParameters.h"
#include "RMLPositionOutputParameters.h"

#ifndef safety_shield_H
#define safety_shield_H

namespace safety_shield {

/**
 * @brief Computes the failsafe trajectory
 */
class SafetyShield {
 private:

  /**
   * @brief Robot reachable set calculation object
   * 
   */
  RobotReach* robot_reach_;

  /**
   * @brief Human reachable set calcualtion object
   * 
   */
  HumanReach* human_reach_;

  /**
   * @brief Verify ISO object
   * 
   * Takes the robot and human capsules as input and checks them for collision.
   */
  Verify* verify_;

  /**
   * @brief Translates the robot motion command to a ROS signal and sends it via a ROS topic.
   * 
   */
  ControlCommandTranslator* translator_;

  /**
   * @brief The rviz visualization of reachable sets
   * 
   */
  RvizMarker* rviz_;

  /**
   * @brief path to go back to the long term plan
   */
  Path recovery_path_;

  /**
   * @brief fail-safe path of the current path
   */
  Path failsafe_path_;

  /**
   * @brief fail-safe path of the repair path
   */
  Path failsafe_path_2_;

  /**
   * @brief verified safe path
   */
  Path safe_path_;

  /**
   * @brief the constructed failsafe path
   */
  Path potential_path_;

  /**
   * @brief Whether or not to use the formal verification.
   * 
   * If this is set to false, every action is executed regardless of safety.
   */
  bool activate_shield_;

  /**
   * @brief Number of joints of the robot
   */
  int nb_joints_;

  /**
   * @brief sampling time
   */
  double sample_time_;

  /**
   * @brief the number of samples since start
   */
  int path_s_discrete_;

  /**
   * @brief Time since start
   */
  double path_s_;

  /**
   * @brief Was the last timestep safe
   */
  bool is_safe_;

  /**
   * @brief Indicates if the last replanning was successful or not.
   * 
   * Indicates problems in the following statements:
   * - It is not strictly guaranteed that the manoeuvres generated maintain 0 ≤ ṡ ≤ 1. In
   * practice, this is only a problem when s̈ ˙ max or s̈ max change rapidly from one timestep to
   * the next, causing the trajectory of s̈ to “overshoot” 0 or 1. Since at all times we have a
   * failsafe trajectory available, verified in advance, which brings the robot to a safe state, if a
   * proposed short-term plan were to overshoot at any point during the plan, this short-term
   * plan is verified as unsafe and the failsafe trajectory is chosen.
   * - Again, when s̈ ˙ m or s̈ m change rapidly between timesteps, it may occur that |s̈| > s̈ m at
   * the start of a proposed short-term plan. Again, if this occurs, that particular short-term
   * plan is verified as unsafe and the failsafe trajectory is chosen.
   */
  bool recovery_path_correct_ = false;
  
  /**
   * @brief The last published motion
   */
  custom_robot_msgs::Motion next_motion_;

  /**
   * @brief The new long term goal 
   */
  Motion new_goal_motion_;

  /**
   * @brief the maximum time to stop 
   */
  const double max_s_stop_;

  /**
   * @brief the maximum time to stop in timesteps (discrete)
   */
  int sliding_window_k_;

  /**
   * @brief Max angle (absolute)
   */
  const double max_q = 3.1;

  /**
   * @brief maximum velocity allowed
   */
  const std::vector<double> v_max_allowed_;
  
  /**
   * @brief maximum acceleration allowed
   */
  const std::vector<double> a_max_allowed_;
  
  /**
   * @brief maximum jerk allowed
   */
  const std::vector<double> j_max_allowed_;
  
  /**
   * @brief maximum acceleration along the long term plan
   */
  const std::vector<double> a_max_ltt_;
  
  /**
   * @brief maximum jerk along the long term plan
   */
  const std::vector<double> j_max_ltt_;
  
  /**
   * @brief the stored long_term_trajectory
   */
  LongTermTraj long_term_trajectory_;

  /**
   * @brief new LTT that wants to override the current LTT
   */
  LongTermTraj new_long_term_trajectory_;

  /**
   * @brief indicates that there is a potential new LTT
   */
  bool new_ltt_ = false;

  /**
   * @brief indicates that there is a new goal to compute a new LTT.
   * 
   * We need a differentation between new goal and new LTT because an LTT to a new goal can only be calculated if the accerlation and jerk values are within the LTT planning bounds.
   */
  bool new_goal_ = false;

  /**
   * @brief indicates that the new LTT was passed to the safety verification at least once.
   */
  bool new_ltt_processed_ = false;

  /**
   * @brief the last starting position of the replanning
   * 
   * If the last starting position of the replanning is very close to this position, we can skip the replanning and use the previously planned trajectory.
   */
  custom_robot_msgs::Motion last_replan_start_motion_;

  /**
   * @brief   motion publisher
   */
  ros::Publisher motion_pub_;

  /**
   * @brief the time when the loop begins
   */
  ros::Time cycle_begin_time_;


  //////// For replanning new trajectory //////
  /**
   * @brief Trajecotry planning object
   */
  ReflexxesAPI* reflexxes_RML_ =	NULL;

  /**
   * @brief Define trajectory planning input parameters here
   */
  RMLPositionInputParameters* reflexxes_IP_ = NULL;

  /**
   * @brief Pointer to safe the trajectroy planning output to 
   */
  RMLPositionOutputParameters* reflexxes_OP_	=	NULL;
  
  /**
   * @brief Trajecory planning flags
   */
  RMLPositionFlags reflexxes_flags_;

  /**
   * @brief Extracts the point of time s (or interpolates it) from the buffer
   *
   * @param s the point's time
   * @param ds the percentage of the maximum path velocity, 0 = stand still, 1 = full velocity
   * @param dds the derivative of ds, 1 = accelerate from v=0 to full velocity in 1 second
   * @param trajectory the long term trajectory to interpolate from
   * @return the motion at point s in trajectory
   */
  custom_robot_msgs::Motion interpolateFromTrajectory(double s, double ds, double dds, 
      const LongTermTraj& trajectory) const;
  
  /**
   * @brief Calculate max acceleration and jerk based on previous velocity
   * 
   * @param[in] prev_speed vector of previous joint velocities
   * @param[in] a_max_part max acceleration for this part of the LTT
   * @param[in] j_max_part max jerk for this part of the LTT
   * @param[out] a_max_manoeuvre Maximum path acceleration
   * @param[out] j_max_manoeuvre Maximum path jerk
   */
  void calculateMaxAccJerk(const std::vector<double> &prev_speed, const std::vector<double>& a_max_part, const std::vector<double>& j_max_part, double& a_max_manoeuvre, double& j_max_manoeuvre);


  /**
   * @brief Computes the fail-safe path
   * 
   * @param[in] pos,vel,acc the starting point caracteristics
   * @param[in] ve the desired final velocity
   * @param[in] a_max the maximum acceleration allowed
   * @param[in] j_max the maximum jerk allowed
   * @param[out] path the new path
   * @return Whether the planning was successful or not
   */
  bool planSafetyShield(double pos, double vel, double acc, double ve, double a_max, double j_max, 
      Path &path);

  /**
   * @brief Calculate the next desired joint position based on verification of recovery path.
   * @param is_safe Last recovery path + potential path are verified safe.
   * @return next motion
   */
  custom_robot_msgs::Motion determineNextMotion(bool is_safe);

  /**
   * @brief Publish a motion command.
   * @param[in] motion The motion command to publish
   */ 
  void publishMotion(const custom_robot_msgs::Motion& motion);

  /**
   * @brief round a continuous time to a timestep
   * @param t continuous time
   * @return timestep 
   */
  inline double roundToTimestep(double t) { return ceil(t/sample_time_)*sample_time_; }

  /** 
   * @brief Calculates and returns the current motion
   */
  custom_robot_msgs::Motion getCurrentMotion();

  /**
   * @brief Determines if the current motion is in the acceleration bounds for replanning
   * 
   * @param current_motion current motion
   * @returns bool: if the current motion lies in the bounds for replanning
   */
  bool checkCurrentMotionForReplanning(const custom_robot_msgs::Motion& current_motion);

  /**
   * @brief Calculates a new trajectory from current joint state to desired goal state.
   * @param goal_q The desired joint angles
   * @param goal_dq The desired joint velocity at the goal position
   * @return Long term trajectory
   */
  LongTermTraj calculateLongTermTrajectory(const std::vector<double>& start_q, const std::vector<double> start_dq, const std::vector<double> start_ddq,
      const std::vector<double>& goal_q, const std::vector<double> goal_dq);
 
 public:
  /**
   * @brief Default contructor
   * 
   */
  SafetyShield():
    max_s_stop_(0),
    v_max_allowed_({0, 0, 0}),
    a_max_allowed_({0, 0, 0}),
    j_max_allowed_({0, 0, 0}),
    a_max_ltt_({0, 0, 0}),
    j_max_ltt_({0, 0, 0})
  {}

  /**
   * @brief Construct a new Safety Shield object
   * 
   * @param activate_shield Wether to activate the safety functionality or not.
   * @param nb_joints Number of joints of the robot
   * @param sample_time Sample time of safety shield
   * @param t_buff Length of the trajectory buffer
   * @param max_s_stop Maximal path length to stop the robot
   * @param v_max_allowed Maximal allowed joint speed
   * @param a_max_allowed Maximal allowed joint acceleration
   * @param j_max_allowed Maximal allowed joint jerk
   * @param a_max_path Maximal allowed relative path acceleration
   * @param j_max_path Maximal allowed relative path jerk
   * @param long_term_trajectory Fixed trajectory to execute (will be overwritten by new intended goals)
   * @param motion_pub Publishes the robot motion to the ROS topic
   * @param robot_reach Robot reachable set calculation object
   * @param human_reach Human reachable set calculation object
   * @param verify Verification of reachable sets object
   * @param translator Outputs the control command to the robot
   * @param rviz Outputs the visualization to rviz
   */
  SafetyShield(bool activate_shield,
      int nb_joints, 
      double sample_time, 
      double t_buff, 
      double max_s_stop, 
      const std::vector<double> &v_max_allowed, 
      const std::vector<double> &a_max_allowed, 
      const std::vector<double> &j_max_allowed, 
      const std::vector<double> &a_max_path, 
      const std::vector<double> &j_max_path, 
      const LongTermTraj &long_term_trajectory, 
      const ros::Publisher &motion_pub,
      RobotReach* robot_reach,
      HumanReach* human_reach,
      Verify* verify,
      ControlCommandTranslator* translator,
      safety_shield::RvizMarker* rviz);

  /**
   * @brief A SafetyShield destructor
   */
  ~SafetyShield();

  /**
   * @brief Computes the new trajectory depending on dq and if the previous path is safe and publishes it
   * @param v is the previous path safe
   * @param prev_speed the velocity of the previous point
   * @returns start and goal position, velocity, acceleration and time of the computed trajectory to execute.
   */
  custom_robot_msgs::StartGoalMotion computesPotentialTrajectory(bool v, const std::vector<double> &prev_speed);

  /**
   * @brief Gets the information that the next simulation cycle (sample time) has started
   * @param cycle_begin_time ROS timestep of begin of current cycle
   */
  void step(const ros::Time& cycle_begin_time);

  /**
   * @brief Calculates a new trajectory from current joint state to desired goal state.
   * Sets new trajectory as desired new long term trajectory.
   * @param goal_motion Desired joint angles and velocities
   */
  void newLongTermTrajectory(const custom_robot_msgs::MotionConstPtr& goal_motion);

  /**
   * @brief Function to convert RML vector to a std vector
   * @param rml_vec
   * @return std_vec
   */
  std::vector<double> convertRMLVec(const RMLDoubleVector& rml_vec);

};
} // namespace safety_shield

#endif // safety_shield_H
