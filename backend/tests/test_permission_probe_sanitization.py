from backend.scripts.diagnose_opencode_permissions_test import summarize


def test_validator_shape_excludes_all_values_messages_and_unknown_names():
    private='private-token-and-filename'
    result=summarize({'success':False,'error':{'name':'ZodError','issues':[
        {'code':'invalid_type','path':['query','directory'],'message':private,'input':private},
        {'code':private,'path':[private,0],'message':private}]},private:private})
    assert private not in str(result)
    assert result['category']=='ZodError'
    assert result['issues']==[{'code':'invalid_type','path':['query','directory']},
                              {'code':'[other]','path':['[other]','[other]']}]


def test_permission_list_is_counted_without_exposing_commands_or_ids():
    assert summarize([{'id':'private','patterns':['secret command']}])=={'shape':'list','count':1}


def test_malformed_error_cannot_escape_allowlist():
    for payload in [{'name':['private'],'error':'private','issues':'private'},
                    {'issues':[{'code':[],'path':'private'}]}]:
        assert 'private' not in str(summarize(payload))


def test_nested_zod_data_is_classified_without_message_values():
    import json
    payload={'name':'ZodError','data':{'message':json.dumps([
        {'code':'invalid_type','path':['permission'],'message':'private-user-content','input':'private-token'}])}}
    result=summarize(payload)
    assert result['category']=='ZodError' and result['data_fields']==['message']
    assert result['issues']==[{'code':'invalid_type','path':['permission']}]
    assert 'private' not in str(result)


def test_generic_error_name_and_unknown_data_fields_remain_safe():
    result=summarize({'name':'Error','data':{'message':'private','secret-key':'private'}})
    assert result['category']=='Error' and result['data_fields']==['[other]','message']
    assert 'private' not in str(result) and 'secret-key' not in str(result)


def test_message_hints_are_finite_words_never_upstream_content():
    result=summarize({'name':'Error','data':{'message':'Invalid context for permission: secret-token /private/path'}})
    assert result['message_hints']==['context','invalid','permission']
    assert 'secret-token' not in str(result) and '/private/path' not in str(result)
