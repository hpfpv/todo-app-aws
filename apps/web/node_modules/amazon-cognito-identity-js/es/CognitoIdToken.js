function _inheritsLoose(t, o) { t.prototype = Object.create(o.prototype), t.prototype.constructor = t, _setPrototypeOf(t, o); }
function _setPrototypeOf(t, e) { return _setPrototypeOf = Object.setPrototypeOf ? Object.setPrototypeOf.bind() : function (t, e) { return t.__proto__ = e, t; }, _setPrototypeOf(t, e); }
/*!
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import CognitoJwtToken from './CognitoJwtToken';

/** @class */
var CognitoIdToken = /*#__PURE__*/function (_CognitoJwtToken) {
  /**
   * Constructs a new CognitoIdToken object
   * @param {string=} IdToken The JWT Id token
   */
  function CognitoIdToken(_temp) {
    var _ref = _temp === void 0 ? {} : _temp,
      IdToken = _ref.IdToken;
    return _CognitoJwtToken.call(this, IdToken || '') || this;
  }
  _inheritsLoose(CognitoIdToken, _CognitoJwtToken);
  return CognitoIdToken;
}(CognitoJwtToken);
export { CognitoIdToken as default };