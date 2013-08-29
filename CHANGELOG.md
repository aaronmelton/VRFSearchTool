# VRFSearchTool.py #
---

## VRFSearchTool v0.0.16-beta (2013-08-29) ##
* Added basic logging to file to track results if application has to connect
  to a router to run buildIndex().
* Suppressed error SPAM from stdout by adding stderr=(open(os.devnull, 'w'))
  to the Queue() function. (Errors are still written to the log.)

## VRFSearchTool v0.0.15-beta (2013-08-28) ##
* Added functionality to specify configFile from the command line.
* Updated README.md

## VRFSearchTool v0.0.14-beta (2013-08-26) ##
* Updated README.md, VRFSearchTool.png, TODO.md, code comments to reflect current 
  functionality.  Removed unused modules.

## VRFSearchTool v0.0.13-beta (2013-08-20) ##
* Adjusted output spacing (removing/moving 'print' statements)
* Added additional comments to code, configFile, routerFile.
* Added configFile functionality to give application the ability to retrieve
  user-specified settings from a config file.  Application use now extended
  such that the list of routers, index and respective paths can be specified
  in the file.  Application can also use configured username and password.

## VRFSearchTool v0.0.12-beta (2013-08-16) ##
* Updated error messages so they reflect the actual filename as read
  from the configFile.
* Rewrote "Building index..." message so it does not take up most of the
  screen when working with a large batch of routers.
  
## VRFSearchTool v0.0.11-beta (2013-08-15) ##
* Cleaned up module importing

## VRFSearchTool v0.0.10-beta (2013-08-15) ##
* Alphabetized functions

  ## VRFSearchTool v0.0.10-beta (2013-08-12) ##
* Changes implemented in v0.0.9-alpha corrected all known bugs; Pushing 
  application into 'beta' status for production environments.
  
## VRFSearchTool v0.0.9-alpha (2013-07-31) ##
* Creating temporary new branch to correct Issue #1 & Issue #2

## VRFSearchTool v0.0.8-alpha (2013-07-29) ##
* Updated CHANGELOG.md, README.md, TODO.md
* Minor corrections to code comments

## VRFSearchTool v0.0.7-alpha (2013-07-27) ##
* Added error checking for user input.  Also fixed application crashing when
  accepting input < 2 characters from user.
* Removed unnecessary debugging commands (no longer needed to trace flow
  of function calls).
* Extended spacing for output table to fit longer VRF Names (up to 20 characters)

## VRFSearchTool v0.0.6-alpha (2013-07-25) ##
* Alpha release of the tool.  Still requires some error checking, code clean-up
  and commenting but otherwise is a working application.

## VRFSearchTool v0.0.1-alpha (2013-07-12) ##
* Initial commit of support files
