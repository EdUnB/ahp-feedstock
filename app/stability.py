"""Analytical boundaries of fixed-priority, three-weight sensitivity.

Only geometry is computed here. Candidate priorities/ranking use engine calls.
"""
from ahp_feedstock.core import aggregate, rank

TIE_TOL = 1e-9


def path_weights(base, index, value):
    others = [j for j in range(3) if j != index]
    remaining = sum(base[j] for j in others)
    result = [0., 0., 0.]
    result[index] = value
    result[others[0]] = (1-value)*(base[others[0]]/remaining if remaining > 0 else .5)
    result[others[1]] = 1-value-result[others[0]]
    return result


def analytical_stability(base, vectors, classes):
    """Partition each OAT path at every equality and tie-tolerance crossing."""
    paths = {}
    for i in range(3):
        start = aggregate(path_weights(base, i, 0), vectors)
        end = aggregate(path_weights(base, i, 1), vectors)
        cuts = {0., 1.}
        for a in range(len(classes)):
            for b in range(a+1, len(classes)):
                intercept = float(start[a]-start[b])
                slope = float(end[a]-end[b])-intercept
                if slope == 0:
                    continue
                for target in [-TIE_TOL, 0., TIE_TOL]:
                    value = (target-intercept)/slope
                    if 0 < value < 1:
                        cuts.add(value)
        cuts = sorted(cuts)
        intervals = []
        for left, right in zip(cuts, cuts[1:]):
            middle = (left+right)/2
            candidate = rank(aggregate(path_weights(base, i, middle), vectors), classes)
            label = (candidate['winner'], candidate['tie'])
            if intervals and (intervals[-1]['winner'], intervals[-1]['tie']) == label:
                intervals[-1]['upper'] = right
            else:
                intervals.append({'lower':left,'upper':right,'winner':label[0],'tie':label[1]})
        paths[f'C{i+1}'] = {
            'intervals':intervals,
            'breakpoints':cuts,
            'boundary_candidates':[{'weight':x,'candidate':rank(aggregate(path_weights(base,i,x),vectors),classes)} for x in cuts],
            'endpoint_rule':'Intervals describe open interiors. Exact boundary results are exported separately; floating-point effects may affect boundary assignment.'}

    # Clip the simplex in (w1,w2) coordinates against P_a-P_b >= tolerance.
    # Vertices describe the closure; unique-winner membership is strictly > tol.
    regions = []
    for a, name in enumerate(classes):
        polygon = [[1.,0.],[0.,1.],[0.,0.]]
        inequalities = []
        for b, other in enumerate(classes):
            if a == b:
                continue
            d = [float(row[a]-row[b]) for row in vectors]
            inequalities.append({'against':other,'coefficients':d,'greater_than':TIE_TOL})
            def distance(p):
                return d[0]*p[0]+d[1]*p[1]+d[2]*(1-p[0]-p[1])-TIE_TOL
            clipped = []
            if polygon:
                for p,q in zip(polygon,polygon[1:]+polygon[:1]):
                    fp,fq = distance(p),distance(q)
                    if fp >= 0:
                        clipped.append(p)
                    if (fp >= 0) != (fq >= 0):
                        t = fp/(fp-fq)
                        clipped.append([p[j]+t*(q[j]-p[j]) for j in range(2)])
            polygon = clipped
        regions.append({'winner':name,'inequalities':inequalities,
                        'vertices':[[p[0],p[1],1-p[0]-p[1]] for p in polygon]})
    return {'paths':paths,'regions':regions,'tie_tolerance':TIE_TOL,
            'method':'Linear priority differences; analytical intersections and half-plane clipping in float64.',
            'domain':'Nonnegative C1,C2,C3 weights summing to one; fixed local priorities.',
            'region_boundary_rule':'Unique winner requires every priority difference > tie tolerance. Polygon edges show closures; the remaining simplex is the tie region.'}
