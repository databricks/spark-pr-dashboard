// jscs:disable
/**
 * Core entry point for the application
 */
define([
  'jquery',
  'react',
  'views/AppManager'
],
function($, React, AppManager) {
  "use strict";

  // jscs:enable
  // Called when a user clicks the "Test with Jenkins" button:
  function testJenkins(number) {
    return confirm("Are you sure you want to test PR " + number + " with Jenkins?");
  }

  // Initialization code to run on page load
  $(function() {
    React.render(AppManager({history: true}), $('#app-manager')[0]);
  });

});
