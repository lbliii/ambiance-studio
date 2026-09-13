"""Public read-only workflow routes with explicit report-output ownership."""
from pathlib import Path
from .command_output import Output, add_output


def add_selectors(parser):
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--subject',choices=['working','review','release'])
    group.add_argument('--revision')
    parser.add_argument('--edition');parser.add_argument('--view')


def add_projection_options(parser, *, limit=3):
    parser.add_argument('--details',action='store_true')
    parser.add_argument('--limit',type=int,default=limit);parser.add_argument('--offset',type=int,default=0)
    parser.add_argument('--kind');parser.add_argument('--subject-limit',type=int,default=6);parser.add_argument('--subject-offset',type=int,default=0)


def add_parsers(sub):
    group=sub.add_parser('workflow',help='Advisory stage and exact-subject action inspection').add_subparsers(dest='action',required=True)
    for name in ['inspect','stage','explain']:
        parser=group.add_parser(name)
        add_selectors(parser);add_output(parser,Output.REPORT,type=Path)
        if name=='stage':parser.add_argument('stage')
        else:parser.add_argument('--stage')
        if name=='explain':
            parser.add_argument('id');parser.add_argument('--expect-assessment')
        else:add_projection_options(parser)


def selectors(args):
    return {key:getattr(args,key,None) for key in ['subject','revision','edition','view','stage']}


def run(args, project):
    from . import workflow
    if args.action=='explain':return workflow.explain(project,args.id,args.expect_assessment,**selectors(args))
    return workflow.inspect(project,**selectors(args),**{key:getattr(args,key) for key in ['details','limit','offset','kind','subject_limit','subject_offset']})
