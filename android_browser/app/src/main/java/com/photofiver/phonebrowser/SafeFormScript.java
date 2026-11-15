package com.photofiver.phonebrowser;

import org.json.JSONObject;

/** Limited, public-page text entry and GET search forms. Never accepts passwords or POST forms. */
final class SafeFormScript {
    private SafeFormScript() {}

    static String fill(String selector, String value) {
        return "(()=>{"
            + "const el=document.querySelector(" + JSONObject.quote(selector) + ");"
            + "if(!el)return 'FIELD_NOT_FOUND';"
            + "const type=(el.getAttribute('type')||'text').toLowerCase();"
            + "const tag=el.tagName.toLowerCase();"
            + "if(!(tag==='textarea'||(tag==='input'&&(type==='text'||type==='search'))))return 'FIELD_TYPE_BLOCKED';"
            + "if(el.disabled||el.readOnly)return 'FIELD_READ_ONLY';"
            + "if(/password|passcode|otp|secret|token|card|pin|bank|account|security|email|phone/i.test("
            + "[el.name,el.id,el.autocomplete].join(' ')))return 'SENSITIVE_FIELD_BLOCKED';"
            + "if(el.form&&el.form.querySelector('input[type=password]'))return 'LOGIN_FORM_BLOCKED';"
            + "try{const proto=(tag==='textarea'?HTMLTextAreaElement:HTMLInputElement).prototype;"
            + "Object.getOwnPropertyDescriptor(proto,'value').set.call(el,"
            + JSONObject.quote(value) + ");"
            + "el.dispatchEvent(new Event('input',{bubbles:true}));"
            + "el.dispatchEvent(new Event('change',{bubbles:true}));"
            + "return el.value===" + JSONObject.quote(value) + "?'FILLED':'VALUE_NOT_SET';"
            + "}catch(e){return 'FILL_ERROR';}"
            + "})()";
    }

    static String submitSearch(String selector) {
        return "(()=>{"
            + "const f=document.querySelector(" + JSONObject.quote(selector) + ");"
            + "if(!f||f.tagName!=='FORM')return 'FORM_NOT_FOUND';"
            + "if((f.getAttribute('method')||'get').toLowerCase()!=='get')return 'POST_FORM_BLOCKED';"
            + "if(f.querySelector('input[type=password],input[type=file]'))return 'SENSITIVE_FORM_BLOCKED';"
            + "if(!f.querySelector('input[type=search],input[type=text],input:not([type]),textarea'))return 'NOT_A_SEARCH_FORM';"
            + "if([...f.querySelectorAll('input,textarea')].some(e=>"
            + "/password|passcode|otp|secret|token|card|pin|bank|account|security|email|phone/i.test("
            + "[e.name,e.id,e.autocomplete].join(' '))))return 'SENSITIVE_FORM_BLOCKED';"
            + "try{const u=new URL(f.getAttribute('action')||location.href,location.href);"
            + "if(u.protocol!=='https:'||u.origin!==location.origin||u.username||u.password)return 'UNSAFE_FORM_ACTION';"
            + "if(/(^|[\\/\\?&=_-])(delete|remove|erase|reset|logout|cancel|purchase|buy|checkout|pay|transfer|withdraw|deposit|trade|sell|order|unsubscribe)(?=$|[\\/\\?&=_-])/i.test(u.pathname+u.search))return 'UNSAFE_FORM_ACTION';"
            + "f.requestSubmit();return 'SUBMITTED';"
            + "}catch(e){return 'SUBMIT_ERROR';}"
            + "})()";
    }
}
