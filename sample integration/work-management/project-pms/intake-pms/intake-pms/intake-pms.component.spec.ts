import { ComponentFixture, TestBed } from '@angular/core/testing';

import { IntakePmsComponent } from './intake-pms.component';

describe('IntakePmsComponent', () => {
  let component: IntakePmsComponent;
  let fixture: ComponentFixture<IntakePmsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ IntakePmsComponent ]
    })
    .compileComponents();

    fixture = TestBed.createComponent(IntakePmsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
