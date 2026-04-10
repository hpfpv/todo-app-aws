function _inheritsLoose(t, o) { t.prototype = Object.create(o.prototype), t.prototype.constructor = t, _setPrototypeOf(t, o); }
function _setPrototypeOf(t, e) { return _setPrototypeOf = Object.setPrototypeOf ? Object.setPrototypeOf.bind() : function (t, e) { return t.__proto__ = e, t; }, _setPrototypeOf(t, e); }
/*!
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import CognitoJwtToken from './CognitoJwtToken';

/** @class */
var CognitoAccessToken = /*#__PURE__*/function (_CognitoJwtToken) {
  /**
   * Constructs a new CognitoAccessToken object
   * @param {string=} AccessToken The JWT access token.
   */
  function CognitoAccessToken(_temp) {
    var _ref = _temp === void 0 ? {} : _temp,
      AccessToken = _ref.AccessToken;
    return _CognitoJwtToken.call(this, AccessToken || '') || this;
  }
  _inheritsLoose(CognitoAccessToken, _CognitoJwtToken);
  return CognitoAccessToken;
}(CognitoJwtToken);
export { CognitoAccessToken as default };